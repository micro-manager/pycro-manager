package org.micromanager.lightsheet;

import ij.ImageJ;
import ij.ImagePlus;
import ij.ImageStack;
import ij.process.ImageProcessor;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.Spliterator;
import java.util.Spliterators;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;
import java.util.stream.StreamSupport;
import mmcorej.TaggedImage;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.util.ImageProcessorBase;

public class ObliqueStackProcessor  {

   public static final int YX_PROJECTION = 0;
   public static final int OTHOGONAL_VIEWS = 1;
   public static final int FULL_VOLUME = 2;
   private final int mode_;

   private double theta;
   private int numZStackSlices_, cameraImageWidth_, cameraImageHeight_;
   private double cameraPixelSizeXY_um_, zStep_um_;
   private double[] imageYCoords_um_, imageZCoords_um_;
   private double reconstructionVoxelSize_um_;
   private int reconstructedImageWidth_, reconstructedImageHeight_, reconstructedImageDepth_;

   private Object[][] lineLocks_;

   private final int[][] reconYCoordLUT_, reconZCoordLUT_;

   int[][] sumProjectionYX_ = null, sumProjectionZY_ = null, sumProjectionZX_ = null;
   int[][][] sumReconVolumeZYX_ = null;
   short[] meanProjectionYX_ = null, meanProjectionZY_ = null, meanProjectionZX_ = null;
   short[][] reconVolumeZYX_ = null;

   int[][] pixelCountSumProjectionYX_, pixelCountSumProjectionZX_, pixelCountSumProjectionZY_;
   int[][][] pixelCountReconVolumeZYX_;

   private BlockingQueue<TaggedImage> imageQueue_ = new LinkedBlockingDeque<>();


   public ObliqueStackProcessor(int mode, double theta, double cameraPixelSizeXyUm, double zStep_um,
                                int zStackSlices, int cameraImageWidth, int cameraImageHeight) {
      this.mode_ = mode;
      this.theta = theta;
      this.numZStackSlices_ = zStackSlices;
      this.cameraImageWidth_ = cameraImageWidth;
      this.cameraImageHeight_ = cameraImageHeight;
      this.cameraPixelSizeXY_um_ = cameraPixelSizeXyUm;
      this.zStep_um_ = zStep_um;
      computeRemappedCoordinateSpace();
      lineLocks_ = new Object[reconstructedImageDepth_][reconstructedImageHeight_];
        for (int i = 0; i < reconstructedImageDepth_; i++) {
             for (int j = 0; j < reconstructedImageHeight_; j++) {
                lineLocks_[i][j] = new Object();
             }
        }
      reconYCoordLUT_ = new int[numZStackSlices_][cameraImageHeight_];
      reconZCoordLUT_ = new int[numZStackSlices_][cameraImageHeight_];
      precomputeCoordTransformLUTs();

      precomputeProjectionPixelCount();
   }

   private void precomputeProjectionPixelCount() {

      if (mode_ == YX_PROJECTION) {
         pixelCountSumProjectionYX_ =  new int[reconstructedImageHeight_][reconstructedImageWidth_];
      } else if (mode_ == OTHOGONAL_VIEWS) {
         pixelCountSumProjectionYX_ =  new int[reconstructedImageHeight_][reconstructedImageWidth_];
         pixelCountSumProjectionZX_ =  new int[reconstructedImageDepth_][reconstructedImageWidth_];
         pixelCountSumProjectionZY_ =  new int[reconstructedImageDepth_][reconstructedImageHeight_];
      } else if (mode_ == FULL_VOLUME) {
         pixelCountReconVolumeZYX_ =  new int[reconstructedImageDepth_][reconstructedImageHeight_][reconstructedImageWidth_];
      }

      for (int cameraZIndex = 0; cameraZIndex < numZStackSlices_; cameraZIndex++) {
         for (int cameraYIndex = 0; cameraYIndex < cameraImageHeight_; cameraYIndex++) {
            int reconYIndex = reconYCoordLUT_[cameraZIndex][cameraYIndex];
            int reconZIndex = reconZCoordLUT_[cameraZIndex][cameraYIndex];
            // X coords are identical in the two views but ys are remapped
            for (int reconXIndex = 0; reconXIndex < reconstructedImageWidth_; reconXIndex++) {
               if (mode_ == YX_PROJECTION) {
                  pixelCountSumProjectionYX_[reconYIndex][reconXIndex] += 1;
               } else if (mode_ == OTHOGONAL_VIEWS) {
                  pixelCountSumProjectionYX_[reconYIndex][reconXIndex] += 1;
                  pixelCountSumProjectionZX_[reconZIndex][reconXIndex] += 1;
                  pixelCountSumProjectionZY_[reconZIndex][reconYIndex] += 1;
               } else if (mode_ == FULL_VOLUME) {
                  pixelCountReconVolumeZYX_[reconZIndex][reconYIndex][reconXIndex] += 1;
               }
            }
         }
      }
   }



   public int getReconstructedImageWidth() {
      return reconstructedImageWidth_;
   }

   public int getReconstructedImageHeight() {
      return reconstructedImageHeight_;
   }

   public int getReconstructedImageDepth() {
      return reconstructedImageDepth_;
   }

   private double[] computeReconstructionCoordsUm(double imageZUm, double cameraYRelative_um) {
      double delta = Math.tan(theta) * imageZUm;
      double cameraYAbsolute_um = cameraYRelative_um + delta;
      double reconYUm = cameraYAbsolute_um * Math.sin(theta);
      double reconZUm = imageZUm * Math.cos(theta);
      return new double[] {reconYUm, reconZUm};
   }

   /*
    * compute the coordinates in um of pixels in the image
    */
   private void computeRemappedCoordinateSpace() {
      imageYCoords_um_ = new double[cameraImageHeight_];
      for (int i = 0; i < cameraImageHeight_; i++) {
         imageYCoords_um_[i] = i * cameraPixelSizeXY_um_;
      }
      imageZCoords_um_ = new double[numZStackSlices_];
      for (int i = 0; i < numZStackSlices_; i++) {
         imageZCoords_um_[i] = i * zStep_um_;
      }
      // compute the um extent of reconstructions coordinates, which is the new XYZ coordinate space
      // that images will be remapped to
      double[] minReconCoords = computeReconstructionCoordsUm(imageZCoords_um_[0], imageYCoords_um_[0]);
      double[] maxReconCoords = computeReconstructionCoordsUm(imageZCoords_um_[numZStackSlices_ - 1],
            imageYCoords_um_[cameraImageHeight_ - 1]);
      double totalReconExtentY_um = maxReconCoords[0] - minReconCoords[0];
      double totalReconExtentZ_um = maxReconCoords[1] - minReconCoords[1];

      // Figure out the shape of the remapped image
      // The x pixel size is fixed by the camera/optics.
      // Make z and y pixels sizes equal to this for isotropic voxels in reconstructions/projections
      reconstructionVoxelSize_um_ = cameraPixelSizeXY_um_;
      reconstructedImageHeight_ = (int) (totalReconExtentY_um / reconstructionVoxelSize_um_);
      reconstructedImageWidth_ = cameraImageWidth_;
      reconstructedImageDepth_ = (int) (totalReconExtentZ_um / reconstructionVoxelSize_um_);
   }

   /**
    * Create look up tables that say which YZ pixels in the camera image correspond to which
    * YZ pixels in the reconstructed image. Not needed for X pixels because they map 1 to 1
    */
   private void precomputeCoordTransformLUTs() {
      for (int zIndexCamera = 0; zIndexCamera < numZStackSlices_; zIndexCamera++) {
         double imageZUm = imageZCoords_um_[zIndexCamera];
         for (int yIndexCamera = 0; yIndexCamera < cameraImageHeight_; yIndexCamera++) {
            double imageYUm = imageYCoords_um_[yIndexCamera];
            double[] reconCoords_um = computeReconstructionCoordsUm(imageZUm, imageYUm);

            int reconYIndex = Math.min(
                  (int) Math.round(reconCoords_um[0] / this.cameraPixelSizeXY_um_),
                  reconstructedImageHeight_ - 1);
            int reconZIndex = Math.min(
                  (int) Math.round(reconCoords_um[1] / this.cameraPixelSizeXY_um_),
                  reconstructedImageDepth_ - 1);

            reconYCoordLUT_[zIndexCamera][yIndexCamera] = reconYIndex;
            reconZCoordLUT_[zIndexCamera][yIndexCamera] = reconZIndex;
         }
      }
   }

   /**
    * This is where the meat of the processing occurs. For each line in the camera image, we
    * look up the corresponding line in the reconstructed image and add the pixel values
    * together.
    *
    * @param image
    * @param zStackIndex
    */
   public void computeImageContributionsToReconstructions(short[] image, int zStackIndex) {
      // loop through all the lines on the image, each of which corresponds to a
      // different axial distance along the sheet
      for (int yIndexCamera = 0; yIndexCamera < cameraImageHeight_; yIndexCamera++) {
         // look up the Y and Z coordinates in the reconstructed image space
         int reconYIndex = reconYCoordLUT_[zStackIndex][yIndexCamera];
         int reconZIndex = reconZCoordLUT_[zStackIndex][yIndexCamera];
         // Now copy a full line of pixels from the camera image to the reconstructed image
         // Only write to one line at a time
         synchronized (lineLocks_[reconZIndex][reconYIndex]) {
            for (int reconXIndex = 0; reconXIndex < cameraImageWidth_; reconXIndex++) {
               short pixelValue = image[yIndexCamera * cameraImageWidth_ + reconXIndex];
               if (sumProjectionYX_ != null) {
                  sumProjectionYX_[reconYIndex][reconXIndex] += (pixelValue & 0xffff);
               }
               if (sumProjectionZY_ != null) {
                  sumProjectionZY_[reconZIndex][reconYIndex] += (pixelValue & 0xffff);
               }
                if (sumProjectionZX_ != null) {
                    sumProjectionZX_[reconZIndex][reconXIndex] += (pixelValue & 0xffff);
                }
                if (sumReconVolumeZYX_ != null) {
                    sumReconVolumeZYX_[reconZIndex][reconYIndex][reconXIndex] += (pixelValue & 0xffff);
                }
            }
         }
      }

   }

   public short[] getYXProjection() {
      return meanProjectionYX_;
   }

    public short[] getZYProjection() {
        return meanProjectionZY_;
    }

    public short[] getZXProjection() {
        return meanProjectionZX_;
    }

    public short[][] getReconstructedVolumeZYX() {
        return reconVolumeZYX_;
    }

    void initializeProjections() {
       if (mode_ == YX_PROJECTION) {
          sumProjectionYX_ = new int[reconstructedImageHeight_][reconstructedImageWidth_];
       } else if (mode_ == OTHOGONAL_VIEWS) {
          sumProjectionYX_ = new int[reconstructedImageHeight_][reconstructedImageWidth_];
          sumProjectionZY_ = new int[reconstructedImageDepth_][reconstructedImageHeight_];
          sumProjectionZX_ = new int[reconstructedImageDepth_][reconstructedImageWidth_];
       } else if (mode_ == FULL_VOLUME) {
          sumReconVolumeZYX_ = new int[reconstructedImageDepth_][reconstructedImageHeight_][reconstructedImageWidth_];
       }
       // cleat from any previous run
       meanProjectionZX_ = null;
       meanProjectionZY_ = null;
       meanProjectionYX_ = null;
       reconVolumeZYX_ = null;
    }

    void finalizeProjections() {
       //finalize the projections by dividing by the number of pixels
       if (mode_ == YX_PROJECTION) {
          computeYXMeanProjection();
       } else if (mode_ == OTHOGONAL_VIEWS) {
          computeYXMeanProjection();
          computeZYMeanProjection();
          computeZXMeanProjection();
       } else if (mode_ == FULL_VOLUME) {
          computeReconstructedVolumeZYX();
       }
    }

   private void processAllImages(ArrayList<short[]> stack) {
      initializeProjections();

      // Parallel process all images
      IntStream.range(0, stack.size())
            .parallel()
            .forEach(zStackIndex ->
                    this.computeImageContributionsToReconstructions(stack.get(zStackIndex), zStackIndex));

      finalizeProjections();
   }

   private void computeYXMeanProjection() {
      meanProjectionYX_ = new short[reconstructedImageWidth_ * reconstructedImageHeight_];
      for (int y = 0; y < reconstructedImageHeight_; y++) {
         for (int x = 0; x < reconstructedImageWidth_; x++) {
            if (pixelCountSumProjectionYX_[y][x] > 0) {
               meanProjectionYX_[x + y * reconstructedImageWidth_] =
                     (short) ( sumProjectionYX_[y][x] / pixelCountSumProjectionYX_[y][x]);
            }
         }
      }
   }

    private void computeZXMeanProjection() {
        meanProjectionZX_ = new short[reconstructedImageWidth_ * reconstructedImageDepth_];
        for (int z = 0; z < reconstructedImageDepth_; z++) {
            for (int x = 0; x < reconstructedImageWidth_; x++) {
                if (pixelCountSumProjectionZX_[z][x] > 0) {
                meanProjectionZX_[x + z * reconstructedImageWidth_] =
                        (short) ( sumProjectionZX_[z][x] / pixelCountSumProjectionZX_[z][x]) ;
                }
            }
        }
    }

    private void computeZYMeanProjection() {
        meanProjectionZY_ = new short[reconstructedImageHeight_ * reconstructedImageDepth_];
        for (int z = 0; z < reconstructedImageDepth_; z++) {
            for (int y = 0; y < reconstructedImageHeight_; y++) {
                if (pixelCountSumProjectionZY_[z][y] > 0) {
                meanProjectionZY_[y + z * reconstructedImageHeight_] =
                        (short) ( sumProjectionZY_[z][y] / pixelCountSumProjectionZY_[z][y]) ;
                }
            }
        }
    }

    private void computeReconstructedVolumeZYX() {
        reconVolumeZYX_ = new short[reconstructedImageDepth_][reconstructedImageHeight_ * reconstructedImageWidth_];
        for (int z = 0; z < reconstructedImageDepth_; z++) {
            for (int y = 0; y < reconstructedImageHeight_; y++) {
                for (int x = 0; x < reconstructedImageWidth_; x++) {
                    if (pixelCountReconVolumeZYX_[z][y][x] > 0) {
                        reconVolumeZYX_[z][y * reconstructedImageWidth_ + x] =
                                (short) ( sumReconVolumeZYX_[z][y][x] / pixelCountReconVolumeZYX_[z][y][x]) ;
                    }
                }
            }
        }
    }


   public void addToProcessImageQueue(TaggedImage image) {
      try {
         imageQueue_.put(image);
      } catch (InterruptedException e) {
         e.printStackTrace();
         throw new RuntimeException(e);
      }
   }


   /**
    * Pull images from the queue and process them in parallel until
    * a full z stack is processed or a null pix null tags stop signal is received.
    * The future can be gotten when the stack is finished processing
    */
   Runnable startStackProcessing() {
      Iterator<TaggedImage> iterator = new Iterator<TaggedImage>() {
         private final AtomicInteger processedImages_ = new AtomicInteger(0);
         private volatile boolean stop_ = false;

         @Override
         public boolean hasNext() {
            return !stop_ && processedImages_.get() < numZStackSlices_;
         }

         @Override
         public TaggedImage next() {
            try {
               TaggedImage element;
               while ((element = imageQueue_.poll(1, TimeUnit.MILLISECONDS)) == null) {
                  // Wait for non-null elements
               }
               if (element.tags == null && element.pix == null) {
                  // This is the last image, stop processing
                  stop_ = true;
                  return null;
               }
               processedImages_.incrementAndGet();
               return element;
            } catch (InterruptedException e) {
               throw new RuntimeException(e);
            }
         }
      };

      return () -> StreamSupport.stream(Spliterators.spliterator(iterator, numZStackSlices_,
            Spliterator.ORDERED | Spliterator.IMMUTABLE | Spliterator.NONNULL), true)
            .forEach(taggedImage ->
                    ObliqueStackProcessor.this.computeImageContributionsToReconstructions((short[]) taggedImage.pix,
                            (Integer) AcqEngMetadata.getAxes(taggedImage.tags).get(AcqEngMetadata.Z_AXIS)));
   }





   ////////////////////////////////////////////////////////////////////
   //////////// Testing methods ///////////////////////////////////////
   ////////////////////////////////////////////////////////////////////

   private static int getImageWidth(ImagePlus imagePlus) {
      ImageStack stack = imagePlus.getStack();
      ImageProcessor ip = stack.getProcessor(1);
      return ip.getWidth();
   }

   private static int getImageHeight(ImagePlus imagePlus) {
      ImageStack stack = imagePlus.getStack();
      ImageProcessor ip = stack.getProcessor(1);
      return ip.getHeight();
   }

   private static ArrayList<short[]> loadTiffStack( ImagePlus imagePlus) {
      ArrayList<short[]> images = new ArrayList<>();

      ImageStack stack = imagePlus.getStack();
      int numSlices = stack.getSize();

      for (int i = 1; i <= numSlices; i++) {
         ImageProcessor ip = stack.getProcessor(i);
         short[] pixels = (short[]) ip.getPixels();
         images.add(pixels);
      }

      Collections.reverse(images);
      return images;
   }


   private static short[] testWithAcqEngJInterface(ArrayList<short[]> stack, int imageWidth, int imageHeight,
         int mode, double theta, double pixelSizeXYUm, double zStepUm) {

      int numToTime = 50;

      // convert imageJ to tagged image
      ArrayList<TaggedImage> taggedImages = new ArrayList<>();
      for (int i = 0; i < stack.size(); i++) {
         short[] image = stack.get(i);
         JSONObject tags = new JSONObject();
         try {
            tags.put("Width", imageWidth);
            tags.put("Height", imageHeight);
            JSONObject axes = new JSONObject();
            axes.put(AcqEngMetadata.Z_AXIS, i);
            tags.put("Axes", axes);
         } catch (JSONException e) {
            e.printStackTrace();
         }
         taggedImages.add(new TaggedImage(image, tags));
      }

      // Simulate several z stacks in sequence
      AcqEngJStackProcessors processor = new AcqEngJStackProcessors(
            mode, theta, pixelSizeXYUm, zStepUm, stack.size(), imageWidth, imageHeight, 1);

      TaggedImage result = null;
      for (int i = 0; i < numToTime; i++) {
         long startTime = System.currentTimeMillis();
         for (TaggedImage taggedImage : taggedImages) {
            result = processor.processImage(taggedImage);
         }
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");
      }
      return (short[]) result.pix;
   }

   private static Object testDirect(ArrayList<short[]> stack, int imageWidth, int imageHeight,
         int mode, double theta, double pixelSizeXYUm, double zStepUm) {

      int numToTest = 3;

      ObliqueStackProcessor processor = new ObliqueStackProcessor(
            mode, theta, pixelSizeXYUm, zStepUm, stack.size(), imageWidth, imageHeight);

      for (int i = 0; i < numToTest; i++) {
         long startTime = System.currentTimeMillis();
         processor.processAllImages(stack);
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");

      }
      if (mode == YX_PROJECTION) {
         return processor.getYXProjection();
      } else if (mode == FULL_VOLUME ) {
         return processor.getReconstructedVolumeZYX();
      }
      throw new RuntimeException();
   }

   public static void main(String[] args) {
//      String tiffPath = "C:\\Users\\henry\\Desktop\\demo_snouty.tif";
      String tiffPath = "/Users/henrypinkard/Desktop/rings_test.tif";
      double zStepUm = 0.13;
      double pixelSizeXYUm = 0.116;
      double theta = 1.05 * Math.PI / 4;

      ImagePlus imagePlus = new ImagePlus(tiffPath);
      int imageWidth = getImageWidth(imagePlus);
      int imageHeight = getImageHeight(imagePlus);
      ArrayList<short[]> stack = loadTiffStack(imagePlus);

      // downsample the stack taking every other
//      int downsamplingFactorZ = 2;
//      ArrayList<short[]> downsampledStack = new ArrayList<>();
//        for (int i = 0; i < stack.size(); i++) {
//             if (i % downsamplingFactorZ == 0) {
//                downsampledStack.add(stack.get(i));
//             }
//        }
//        stack = downsampledStack;
//        zStepUm *= downsamplingFactorZ;


      // keep only first 256 elements
//        stack = new ArrayList<short[]>(stack.subList(0, 256));

//         create a new stack of images with teh y axis downsized by a factor of
//      int downsamplingFactor = 4;
//        for (int i = 0; i < stack.size(); i++) {
//             short[] image = stack.get(i);
//             short[] newImage = new short[image.length / downsamplingFactor];
//             for (int j = 0; j < newImage.length; j++) {
//                 newImage[j] = image[j * downsamplingFactor];
//             }
//             stack.set(i, newImage);
//         }
//         imageWidth /= downsamplingFactor;

      System.out.println("Stack size: " + stack.size());
      System.out.println("Image width: " + imageWidth + " Image height: " + imageHeight);



      int mode = ObliqueStackProcessor.FULL_VOLUME;


//      short[] projectionXY = testDirect(stack, imageWidth, imageHeight, mode, theta,
//            pixelSizeXYUm, zStepUm);

      short[][] reconVolume = (short[][]) testDirect(stack, imageWidth, imageHeight, mode, theta,
              pixelSizeXYUm, zStepUm);

//      short[] projectionXY = testWithAcqEngJInterface(stack, imageWidth, imageHeight, mode, theta,
//            pixelSizeXYUm, zStepUm);


      //display in imageJ
      //open the imagej toolbar
      new ImageJ();

      int reconImageDepth = reconVolume.length;
      int reconImageWidth = imageWidth;
      int reconImageHeight = reconVolume[0].length / reconImageWidth;

      ImageStack imageStack = new ImageStack(reconImageWidth, reconImageHeight);
      for (short[] s : reconVolume) {
         imageStack.addSlice("projection", s);
      }
      ImagePlus projectionImage = new ImagePlus("projection", imageStack);
      projectionImage.show();

   }

}

   /**
    * This class allows acqEngJ to call this oblique processor. It splits images
    * from different cameras/channels/etc onto different instances of ObliqueStackProcessor
    */
   class AcqEngJStackProcessors extends ImageProcessorBase {
      // Map from non Z-axes to SingleStackProcessor that is managing the reconstruction for that stack
      private HashMap<HashMap<String, Object>, ObliqueStackProcessor> singleStackProcessors_ = new HashMap<>();

      private ExecutorService processingExecutor_ =
            new ThreadPoolExecutor(1, 12, 1000, TimeUnit.MILLISECONDS,
                    new LinkedBlockingDeque<>());
      private HashMap<HashMap<String, Object>, Future> processingFutures_ = new HashMap<>();

      private LinkedList<ObliqueStackProcessor> freeProcessors_ = new LinkedList<>();

        private final int mode_;
        private final double theta_;
        private final double cameraPixelSizeXyUm_;
        private final double zStep_um_;
        private final int numZStackSlices_;
        private final int cameraImageWidth_;
        private final int cameraImageHeight_;


      public AcqEngJStackProcessors(int mode, double theta, double cameraPixelSizeXyUm, double zStep_um,
                                    int zStackSlices, int cameraImageWidth, int cameraImageHeight,
                                    int numUniqueProcessorsNeeded) {
         super();
         mode_ = mode;
         theta_ = theta;
         cameraPixelSizeXyUm_ = cameraPixelSizeXyUm;
         zStep_um_ = zStep_um;
         numZStackSlices_ = zStackSlices;
         cameraImageWidth_ = cameraImageWidth;
         cameraImageHeight_ = cameraImageHeight;
         for (int i = 0; i < numUniqueProcessorsNeeded; i++) {
            freeProcessors_.add(new ObliqueStackProcessor(mode_, theta_, cameraPixelSizeXyUm_,
                  zStep_um_, numZStackSlices_, cameraImageWidth_, cameraImageHeight_));
         }
      }

      public int getReconstructedImageWidth() {
         return singleStackProcessors_.values().iterator().next().getReconstructedImageWidth();
      }

        public int getReconstructedImageHeight() {
             return singleStackProcessors_.values().iterator().next().getReconstructedImageHeight();
        }

      @Override
      protected TaggedImage processImage(TaggedImage img) {
         // This gets called by acq engine. Sort through non-z axes to determine which
         // processing stack to use.
         int zIndex = (Integer) AcqEngMetadata.getAxes(img.tags).get(AcqEngMetadata.Z_AXIS);
         HashMap<String, Object> nonZAxes = AcqEngMetadata.getAxes(img.tags);
         nonZAxes.remove(AcqEngMetadata.Z_AXIS);

         ObliqueStackProcessor processor = singleStackProcessors_.getOrDefault(nonZAxes, null);

         if (img.tags == null && img.pix == null) {
            // This is the last image because acquisition is ending,
            // tell all processors to stop processing
            for (ObliqueStackProcessor p : singleStackProcessors_.values()) {
               p.addToProcessImageQueue(img);
            }
            processingExecutor_.shutdown();
            return null;
         }


         if (zIndex == 0) {
            singleStackProcessors_.put(nonZAxes, freeProcessors_.pop());
            processor = singleStackProcessors_.get(nonZAxes);

            // First image, initialize the processing
            processor.initializeProjections();
            Future<?> f = processingExecutor_.submit(processor.startStackProcessing());
            processingFutures_.put(nonZAxes, f);
            processor.addToProcessImageQueue(img);
            return null;
         } else if (zIndex == numZStackSlices_ - 1) {
            processor.addToProcessImageQueue(img);
            // It's the final one, wait for processing to complete and propagate the result
            try {
               processingFutures_.get(nonZAxes).get();
            } catch (InterruptedException e) {
               e.printStackTrace();
               throw new RuntimeException();
            } catch (ExecutionException e) {
               e.printStackTrace();
               throw new RuntimeException();
            } finally {
                processingFutures_.remove(nonZAxes);
            }

            processor.finalizeProjections();
            // Return the projection image
            try {
               JSONObject newTags = new JSONObject(img.tags.toString());
               if (newTags.has(AcqEngMetadata.Z_UM_INTENDED)) {
                  newTags.remove(AcqEngMetadata.Z_UM_INTENDED);
               }
               AcqEngMetadata.setAxisPosition(newTags, AcqEngMetadata.Z_AXIS, null);
               AcqEngMetadata.setHeight(newTags, processor.getReconstructedImageHeight());
               AcqEngMetadata.setWidth(newTags, processor.getReconstructedImageWidth());
               short[] projection = processor.getYXProjection();
                freeProcessors_.add(processor);
                singleStackProcessors_.remove(nonZAxes);
                return new TaggedImage(projection, newTags);

            } catch (JSONException e) {
               throw new RuntimeException(e);
            }
         } else {
            processor.addToProcessImageQueue(img);
            return null;
         }
      }

   }


