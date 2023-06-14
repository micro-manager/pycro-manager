package org.micromanager.lightsheet;

import mmcorej.TaggedImage;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.util.ImageProcessorBase;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;


/**
 * This class acts as a bridge between the acquisition engine and the stack resampler. A single
 * StackResampler is needed for each Z stack that is running in parallel (i.e. if multiple) channels
 * are interleaved. So this class creates multiple StackResamplers and manages as needed.
 * It also handles the translation between the ImageProcessor methods of AcqEngJ and the methods
 * of StackResampler. For example, initializing the StackResampler on the first z slice, and finalizing
 * it on the last z slice and adding the result to the oyutput queue.
 */
class StackResamplersImageProcessor extends ImageProcessorBase {

   public static final String RESAMPLE_AXIS_NAME = "Resample";
   public static final String YX_PROJECTION = "YX";
   public static final String ZY_PROJECTION = "ZY";
   public static final String ZX_PROJECTION = "ZX";
   public static final String ZYX_INTERPOLATION = "ZYX";

   private ExecutorService processingExecutor_ =
           new ThreadPoolExecutor(1, 12, 1000, TimeUnit.MILLISECONDS,
                   new LinkedBlockingDeque<>());
   private HashMap<HashMap<String, Object>, Future> processingFutures_ = new HashMap<>();

   private HashMap<String, StackResampler> freeProcessors_ = new HashMap<>();
   private HashMap<HashMap<String, Object>, StackResampler> activeProcessors_ = new HashMap<>();

   private final int mode_;
   private final double theta_;
   private final double cameraPixelSizeXyUm_;
   private final double zStep_um_;
   private final int numZStackSlices_;
   private final int cameraImageWidth_;
   private final int cameraImageHeight_;
   private final boolean returnRawDataAlso_;
   private boolean fuseOrthogonalViews_;

   public StackResamplersImageProcessor(int mode, double theta, double cameraPixelSizeXyUm, double zStep_um,
                                        int zStackSlices, int cameraImageWidth, int cameraImageHeight,
                                        int numProcessorsToPreload, boolean returnRawDataAlso,
                                        boolean fuseOrthogonalViews, boolean doMaxProjection) {
      super();
      mode_ = mode;
      theta_ = theta;
      cameraPixelSizeXyUm_ = cameraPixelSizeXyUm;
      fuseOrthogonalViews_ = fuseOrthogonalViews;
      zStep_um_ = zStep_um;
      numZStackSlices_ = zStackSlices;
      cameraImageWidth_ = cameraImageWidth;
      cameraImageHeight_ = cameraImageHeight;
      returnRawDataAlso_ = returnRawDataAlso;
      for (int i = 0; i < numProcessorsToPreload; i++) {
         StackResampler s = new StackResampler(mode_, doMaxProjection, theta_, cameraPixelSizeXyUm_,
                 zStep_um_, numZStackSlices_, cameraImageWidth_, cameraImageHeight_);
         freeProcessors_.put(s.getSettingsKey(), s);
      }
   }

   /**
    * For testing purposes only
    */
   LinkedBlockingDeque<TaggedImage> getOutputQueue() {
      return sink_;
   }

   public int getResampledShapeX() {
      StackResampler s = freeProcessors_.size() > 0 ? freeProcessors_.values().iterator().next() :
              activeProcessors_.values().iterator().next();
      return s.getResampledShapeX();
   }

   public int getResampledShapeY() {
      StackResampler s = freeProcessors_.size() > 0 ? freeProcessors_.values().iterator().next() :
              activeProcessors_.values().iterator().next();
      return s.getResampledShapeY();
   }

   public int getResampledShapeZ() {
      StackResampler s = freeProcessors_.size() > 0 ? freeProcessors_.values().iterator().next() :
              activeProcessors_.values().iterator().next();
      return s.getResampledShapeZ();
   }

   @Override
   protected TaggedImage processImage(TaggedImage img) {
      try {
         // This gets called by acq engine. Sort through non-z axes to determine which
         // processing stack to use.
         int zIndex = (Integer) AcqEngMetadata.getAxes(img.tags).get(AcqEngMetadata.Z_AXIS);
         HashMap<String, Object> nonZAxes = AcqEngMetadata.getAxes(img.tags);
         nonZAxes.remove(AcqEngMetadata.Z_AXIS);

         if (img.tags == null && img.pix == null) {
            // This is the last image because acquisition is ending,
            // tell all processors to stop processing
            for (StackResampler p : activeProcessors_.values()) {
               p.addToProcessImageQueue(img);
            }
            processingExecutor_.shutdown();
            return null;
         }

         // These params are assumed the same for all stacks for now, but this could be changed later
         String settingsKey = StackResampler.createSettingsKey(mode_, theta_, cameraPixelSizeXyUm_,
                 zStep_um_, numZStackSlices_, cameraImageWidth_, cameraImageHeight_);

         if (zIndex == 0) {
            // First Z slice
            StackResampler processor = freeProcessors_.getOrDefault(settingsKey, null);

            activeProcessors_.put(nonZAxes, processor);

            // First image, initialize the processing
            processor.initializeProjections();
            Future<?> f = processingExecutor_.submit(processor.startStackProcessing());
            processingFutures_.put(nonZAxes, f);
            processor.addToProcessImageQueue(img);
         } else if (zIndex == numZStackSlices_ - 1) {
            // Last Z slice
            StackResampler processor = activeProcessors_.get(nonZAxes);
            processor.addToProcessImageQueue(img);
            // It's the final one, wait for processing to complete and propagate the result
            processingFutures_.get(nonZAxes).get();
            // at this point, the processing of all slices is complete
            processingFutures_.remove(nonZAxes);

            // This call is probably relatively fast
            processor.finalizeProjections();

            // Add the projection/reconstruction images to output
            if (mode_ == StackResampler.YX_PROJECTION) {
               addToOutputQueue(generateYXProjectionTaggedImage(processor, img));
            } else if (mode_ == StackResampler.OTHOGONAL_VIEWS) {
               if (fuseOrthogonalViews_) {
                  addToOutputQueue(generateFusedOrthogonalViews(processor, img));
               } else {
                  addToOutputQueue(generateYXProjectionTaggedImage(processor, img));
                  addToOutputQueue(generateZYProjectionTaggedImage(processor, img));
                  addToOutputQueue(generateZXProjectionTaggedImage(processor, img));
               }
            } else if (mode_ == StackResampler.FULL_VOLUME) {
               for (TaggedImage zSlice : generateReconstructedVolume(processor, img)) {
                  addToOutputQueue(zSlice);
               }
            } else {
               throw new RuntimeException("Unknown mode: " + mode_);
            }
            activeProcessors_.remove(nonZAxes);
            freeProcessors_.put(settingsKey, processor);
         } else {
            // Neither first nor last Z slice
            activeProcessors_.get(nonZAxes).addToProcessImageQueue(img);
         }

         return returnRawDataAlso_ ? img : null;
      } catch (Exception e) {
         e.printStackTrace();
         throw new RuntimeException(e);
      }
   }

   private TaggedImage generateFusedOrthogonalViews(StackResampler processor, TaggedImage img)
      throws JSONException {

      JSONObject newTags = new JSONObject(img.tags.toString());
      // remove tags related to Z
      if (newTags.has(AcqEngMetadata.Z_UM_INTENDED)) {
         newTags.remove(AcqEngMetadata.Z_UM_INTENDED);
      }
      AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, null);

      // fuse the orthogonal views into a single image
      short[] yx = processor.getYXProjection();
      short[] zy = processor.getZYProjection();
      short[] zx = processor.getZXProjection();
      int xSize = processor.getResampledShapeX();
      int ySize = processor.getResampledShapeY();
      int zSize = processor.getResampledShapeZ();

      int fusedWidth = xSize + zSize;
      int fusedHeight = ySize + zSize;
      short[] fused = new short[fusedWidth * fusedHeight];

      // copy YX projection
      for (int i = 0; i < ySize; i++) {
         for (int j = 0; j < xSize; j++) {
            fused[i * fusedWidth + j] = (short) (yx[i * xSize + j] & 0xffff);
         }
      }

      // copy ZY projection
      for (int i = 0; i < ySize; i++) {
         for (int j = 0; j < zSize; j++) {
            fused[i * fusedWidth + (j + xSize)] = (short) (zy[i + ySize * j] & 0xffff);
         }
      }

      // copy ZX projection
      for (int i = 0; i < zSize; i++) {
         for (int j = 0; j < xSize; j++) {
            fused[(i + ySize) * fusedWidth + j] = (short) (zx[i * xSize + j] & 0xffff);
         }
      }


      AcqEngMetadata.setHeight(newTags, fusedHeight);
      AcqEngMetadata.setWidth(newTags, fusedWidth);

      // Add a special tag to indicate that this is a projection
      AcqEngMetadata.setAxisPosition(newTags, RESAMPLE_AXIS_NAME, ZX_PROJECTION);

      return new TaggedImage(fused, newTags);
   }

   private ArrayList<TaggedImage> generateReconstructedVolume(StackResampler processor, TaggedImage img)
      throws JSONException {
      ArrayList<TaggedImage> volume = new ArrayList<>();
      double reconZStep = processor.getReconstructionVoxelSizeUm();
      short[][] reconstructedVolume = processor.getReconstructedVolumeZYX();
      for (int z = 0; z < reconstructedVolume.length; z++) {
         JSONObject newTags = new JSONObject(img.tags.toString());
         AcqEngMetadata.setStageZIntended(newTags, z * reconZStep);
         AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, z);
         AcqEngMetadata.setHeight(newTags, processor.getResampledShapeY());
         AcqEngMetadata.setWidth(newTags, processor.getResampledShapeX());

         // Add a special tag to indicate that this is a projection
         AcqEngMetadata.setAxisPosition(newTags, RESAMPLE_AXIS_NAME, ZYX_INTERPOLATION);
         volume.add(new TaggedImage(reconstructedVolume[z], newTags));
      }
      return volume;
   }

   private TaggedImage generateZXProjectionTaggedImage(StackResampler processor, TaggedImage img)
           throws JSONException {
      JSONObject newTags = new JSONObject(img.tags.toString());
      // remove tags related to Z
      if (newTags.has(AcqEngMetadata.Z_UM_INTENDED)) {
         newTags.remove(AcqEngMetadata.Z_UM_INTENDED);
      }
      AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, null);
      AcqEngMetadata.setHeight(newTags, processor.getResampledShapeZ());
      AcqEngMetadata.setWidth(newTags, processor.getResampledShapeX());

      // Add a special tag to indicate that this is a projection
      AcqEngMetadata.setAxisPosition(newTags, RESAMPLE_AXIS_NAME, ZX_PROJECTION);

      return new TaggedImage(processor.getZXProjection(), newTags);
   }

   private TaggedImage generateZYProjectionTaggedImage(StackResampler processor, TaggedImage img)
            throws JSONException {
      JSONObject newTags = new JSONObject(img.tags.toString());
      // remove tags related to Z
      if (newTags.has(AcqEngMetadata.Z_UM_INTENDED)) {
         newTags.remove(AcqEngMetadata.Z_UM_INTENDED);
      }
      AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, null);
      AcqEngMetadata.setHeight(newTags, processor.getResampledShapeZ());
      AcqEngMetadata.setWidth(newTags, processor.getResampledShapeY());

      // Add a special tag to indicate that this is a projection
      AcqEngMetadata.setAxisPosition(newTags, RESAMPLE_AXIS_NAME, ZY_PROJECTION);

      return new TaggedImage(processor.getZYProjection(), newTags);
   }

   private TaggedImage generateYXProjectionTaggedImage(StackResampler processor, TaggedImage img)
           throws JSONException {
      JSONObject newTags = new JSONObject(img.tags.toString());
      // remove tags related to Z
      if (newTags.has(AcqEngMetadata.Z_UM_INTENDED)) {
         newTags.remove(AcqEngMetadata.Z_UM_INTENDED);
      }
      AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, null);
      AcqEngMetadata.setHeight(newTags, processor.getResampledShapeY());
      AcqEngMetadata.setWidth(newTags, processor.getResampledShapeX());

      // Add a special tag to indicate that this is a projection
      AcqEngMetadata.setAxisPosition(newTags, RESAMPLE_AXIS_NAME, YX_PROJECTION);

      return new TaggedImage(processor.getYXProjection(), newTags);
   }


}

