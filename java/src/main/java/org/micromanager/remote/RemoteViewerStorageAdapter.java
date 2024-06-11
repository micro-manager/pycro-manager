package org.micromanager.remote;

import java.util.HashMap;
import java.util.Set;
import java.util.concurrent.*;
import java.util.function.Consumer;

import mmcorej.TaggedImage;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.api.AcqEngJDataSink;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.internal.Engine;
import org.micromanager.ndtiffstorage.IndexEntryData;
import org.micromanager.ndtiffstorage.NDRAMStorage;
import org.micromanager.ndtiffstorage.NDTiffStorage;
import org.micromanager.ndtiffstorage.MultiresNDTiffAPI;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.NDViewerDataSource;
import org.micromanager.ndviewer.api.NDViewerAPI;
import org.micromanager.ndviewer.main.NDViewer;
import org.micromanager.ndviewer.api.NDViewerAcqInterface;

/**
 * The class is the glue needed in order for Acquisition engine, viewer, and data storage
 * to be able to be used together, since they are independent libraries that do not know about one
 * another. It implements the Acquisition engine API for a {@link AcqEngJDataSink} interface, dispatching acquired images
 * to viewer and storage as appropriate. It implements viewers {@link NDViewerDataSource} interface, so
 * that images in storage can be passed to the viewer to display.
 *
 * @author henrypinkard
 */
class RemoteViewerStorageAdapter implements NDViewerDataSource, AcqEngJDataSink, PycroManagerCompatibleUI {

   private ExecutorService displayCommunicationExecutor_;

   private volatile NDViewerAPI viewer_;
   private volatile Acquisition acq_;
   private volatile NDTiffAPI storage_;
   private final boolean showViewer_, xyTiled_;
   private final int tileOverlapX_, tileOverlapY_;
   private String dir_;
   private String name_;
   private Integer maxResLevel_;
   private int savingQueueSize_;
   private volatile boolean finished_ = false;


   /**
    * @param showViewer          create and show a viewer
    * @param dataStorageLocation where should data be saved to disk
    * @param name                name for data storage and viewer
    * @param xyTiled             true if using XY tiling/multiresolution features
    * @param tileOverlapX        X pixel overlap between adjacent tiles if using XY tiling/multiresolution
    * @param tileOverlapY        Y pixel overlap between adjacent tiles if using XY tiling/multiresolution
    * @param maxResLevel         The maximum resolution level index if using XY tiling/multiresolution
    */
   public RemoteViewerStorageAdapter(boolean showViewer, String dataStorageLocation,
                                     String name, boolean xyTiled, int tileOverlapX,
                                     int tileOverlapY,
                                     Integer maxResLevel, int savingQueueSize) {
      showViewer_ = showViewer;
      xyTiled_ = xyTiled;
      dir_ = dataStorageLocation;
      name_ = name;
      tileOverlapX_ = tileOverlapX;
      tileOverlapY_ = tileOverlapY;
      maxResLevel_ = maxResLevel;
      savingQueueSize_ = savingQueueSize;
   }

   public void initialize(Acquisition acq, JSONObject summaryMetadata) {
      acq_ = acq;


      if (xyTiled_) {
         //tiled datasets have a fixed, acquisition-wide image size
         AcqEngMetadata.setWidth(summaryMetadata, (int) Engine.getCore().getImageWidth());
         AcqEngMetadata.setHeight(summaryMetadata, (int) Engine.getCore().getImageHeight());
      }

      if (dir_ == null) {
         storage_ = new NDRAMStorage(summaryMetadata);
         if (name_ == null) {
            name_ = "In RAM acquisition";
         }
      } else {
         storage_ = new NDTiffStorage(dir_, name_,
               summaryMetadata, tileOverlapX_, tileOverlapY_,
               xyTiled_, maxResLevel_, savingQueueSize_,
               //Debug logging function without storage having to directly depend on core
               acq_.isDebugMode() ? ((Consumer<String>) s -> {
                  Engine.getCore().logMessage(s);
               }) : null, true
         );
         name_ = storage_.getUniqueAcqName();
      }

      if (showViewer_) {
         createDisplay(summaryMetadata);
      }
   }

   @Override
   public NDViewerAPI getViewer() {
      return viewer_;
   }

   public NDTiffAPI getStorage() {
      return storage_;
   }

   private void createDisplay(JSONObject summaryMetadata) {
      //create display
      displayCommunicationExecutor_ = Executors.newSingleThreadExecutor((Runnable r)
              -> new Thread(r, "Image viewer communication thread"));

      viewer_ = new NDViewer(this, (NDViewerAcqInterface) acq_,
              summaryMetadata, AcqEngMetadata.getPixelSizeUm(summaryMetadata), AcqEngMetadata.isRGB(summaryMetadata));

      viewer_.setWindowTitle(name_ + (acq_ != null
              ? (acq_.areEventsFinished()? " (Finished)" : " (Running)") : " (Loaded)"));
      //add functions so display knows how to parse time and z infomration from image tags
      viewer_.setReadTimeMetadataFunction((JSONObject tags) -> AcqEngMetadata.getElapsedTimeMs(tags));
      viewer_.setReadZMetadataFunction((JSONObject tags) -> AcqEngMetadata.getStageZIntended(tags));
   }

   public Object putImage(final TaggedImage taggedImg) {
      HashMap<String, Object> axes = AcqEngMetadata.getAxes(taggedImg.tags);
      final Future<IndexEntryData> added;
      if (xyTiled_) {
         added = ((MultiresNDTiffAPI)storage_).putImageMultiRes(taggedImg.pix, taggedImg.tags, axes,
                 AcqEngMetadata.isRGB(taggedImg.tags),
                 AcqEngMetadata.getBitDepth(taggedImg.tags),
                 AcqEngMetadata.getHeight(taggedImg.tags),
                 AcqEngMetadata.getWidth(taggedImg.tags));
      } else {
         added = storage_.putImage(taggedImg.pix, taggedImg.tags, axes,
                 AcqEngMetadata.isRGB(taggedImg.tags),
                 AcqEngMetadata.getBitDepth(taggedImg.tags),
                 AcqEngMetadata.getHeight(taggedImg.tags),
                 AcqEngMetadata.getWidth(taggedImg.tags));
      }

      if (showViewer_) {
         //put on different thread to not slow down acquisition
         displayCommunicationExecutor_.submit(new Runnable() {
            @Override
            public void run() {
               try {
                  if (xyTiled_) {
                     // This is needed to make sure multi res data at higher
                     // resolutions kept up to date I think because lower resolutions
                     // aren't stored temporarily. This could potentially be
                     // changed in the storage class
                     added.get();
                  }
               } catch (Exception e) {
                  Engine.getCore().logMessage(e.getMessage());
                  throw new RuntimeException(e);
               }
               HashMap<String, Object> axes = AcqEngMetadata.getAxes(taggedImg.tags);
               if (xyTiled_) {
                  //remove this so the viewer doesn't show it
                  axes.remove(AcqEngMetadata.AXES_GRID_ROW);
                  axes.remove(AcqEngMetadata.AXES_GRID_COL);
               }
               viewer_.newImageArrived(axes);
            }
         });
      }
      try {
         Object result = added.get();

         JSONObject json = new JSONObject();
         // Indicate the storage format of the image
         if (storage_ instanceof NDTiffStorage) {
            return result;
         } else if (storage_ instanceof NDRAMStorage) {
            return AcqEngMetadata.serializeAxes(axes);
         } else {
            throw new RuntimeException("Unknown storage type");
         }


      } catch (Exception e) {
         throw new RuntimeException(e);
      }
   }
  
   ///////// Data source interface for Viewer //////////
   @Override
   public int[] getBounds() {
      return storage_.getImageBounds();
   }

   @Override
   public TaggedImage getImageForDisplay(HashMap<String, Object> axes, int resolutionindex,
           double xOffset, double yOffset, int imageWidth, int imageHeight) {

      if (storage_ instanceof MultiresNDTiffAPI) {
         return ((MultiresNDTiffAPI) storage_).getDisplayImage(
                 axes, resolutionindex, (int) xOffset, (int) yOffset,
                 imageWidth, imageHeight);
      } else {
         return storage_.getSubImage(axes, (int) xOffset, (int) yOffset, imageWidth, imageHeight);
      }
   }

   @Override
   public Set<HashMap<String, Object>> getImageKeys() {
      return storage_.getAxesSet();
   }

   @Override
   public int getMaxResolutionIndex() {
      if (storage_ instanceof MultiresNDTiffAPI) {
         return ((MultiresNDTiffAPI) storage_).getNumResLevels() - 1;
      }
      return 0;
   }

   @Override
   public void increaseMaxResolutionLevel(int newMaxResolutionLevel) {
      if (storage_ instanceof MultiresNDTiffAPI) {
         ((MultiresNDTiffAPI) storage_).increaseMaxResolutionLevel(newMaxResolutionLevel);
      }
   }

   @Override
   public String getDiskLocation() {
      return dir_;
   }
   
   public void close() {
      try {
         if (!(storage_ instanceof NDRAMStorage)) {
            // If its RAM storage, the python side may want to hang onto it
            storage_.closeAndWait();
            storage_ = null;
         }
      } catch (InterruptedException e) {
         throw new RuntimeException(e);
      }
   }

   @Override
   public int getImageBitDepth(HashMap<String, Object> axesPositions) {
      return storage_.getEssentialImageMetadata(axesPositions).bitDepth;
   }

   ///////////// Data sink interface required by acq eng /////////////
   @Override
   public void finish() {
      if (storage_ != null) {
         if (!storage_.isFinished()) {
            //Get most up to date display settings
            if (viewer_ != null) {
               JSONObject displaySettings = viewer_.getDisplaySettingsJSON();
               storage_.setDisplaySettings(displaySettings);
            }
            storage_.finishedWriting();
         }
         if (!showViewer_) {
            //If there's no viewer, shutdown of acquisition == shutdown of storage
            close();
         }
      }
      
      if (showViewer_) {
         try {
            storage_.checkForWritingException();
            viewer_.setWindowTitle(name_ + " (Finished)");
         } catch (Exception e) {
            viewer_.setWindowTitle(name_ + " (Finished with saving error)");
         } finally {
            displayCommunicationExecutor_.shutdown();
         }
      }
      finished_ = true;
   }

   @Override
   public boolean isFinished() {
      return finished_;
   }

   @Override
   public boolean anythingAcquired() {
      return acq_.anythingAcquired();
   }

   int getOverlapX() {
      return tileOverlapX_;
   }

   int getOverlapY() {
      return tileOverlapY_;
   }
}
