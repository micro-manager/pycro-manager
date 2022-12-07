/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import java.util.HashMap;
import java.util.Set;
import java.util.concurrent.*;
import java.util.function.Consumer;

import mmcorej.TaggedImage;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.api.DataSink;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.internal.Engine;
import org.micromanager.ndtiffstorage.NDTiffStorage;
import org.micromanager.ndtiffstorage.MultiresNDTiffAPI;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.DataSourceInterface;
import org.micromanager.ndviewer.api.ViewerInterface;
import org.micromanager.ndviewer.main.NDViewer;
import org.micromanager.ndviewer.api.ViewerAcquisitionInterface;

/**
 * The class is the glue needed in order for Acquisition engine, viewer, and data storage
 * to be able to be used together, since they are independent libraries that do not know about one
 * another. It implements the Acquisition engine API for a {@link DataSink} interface, dispatching acquired images
 * to viewer and storage as appropriate. It implements viewers {@link DataSourceInterface} interface, so
 * that images in storage can be passed to the viewer to display.
 *
 * @author henrypinkard
 */
public class RemoteViewerStorageAdapter implements DataSourceInterface, DataSink {

   private ExecutorService displayCommunicationExecutor_;

   private volatile ViewerInterface viewer_;
   private volatile Acquisition acq_;
   private volatile MultiresNDTiffAPI storage_;
   private CopyOnWriteArrayList<String> channelNames_ = new CopyOnWriteArrayList<String>();

   private final boolean showViewer_, storeData_, xyTiled_;
   private final int tileOverlapX_, tileOverlapY_;
   private String dir_;
   private String name_;
   private Integer maxResLevel_;
   private int savingQueueSize_;
   private volatile boolean finished_ = false;


   /**
    *
    * @param showViewer create and show a viewer
    * @param dataStorageLocation where should data be saved to disk
    * @param name name for data storage and viewer
    * @param xyTiled true if using XY tiling/multiresolution features
    * @param tileOverlapX X pixel overlap between adjacent tiles if using XY tiling/multiresolution
    * @param tileOverlapY Y pixel overlap between adjacent tiles if using XY tiling/multiresolution
    * @param maxResLevel The maximum resolution level index if using XY tiling/multiresolution
    */
   public RemoteViewerStorageAdapter(boolean showViewer,  String dataStorageLocation,
                                     String name, boolean xyTiled, int tileOverlapX, int tileOverlapY,
                                     Integer maxResLevel, int savingQueueSize) {
      showViewer_ = showViewer;
      storeData_ = dataStorageLocation != null;
      xyTiled_ = xyTiled;
      dir_ = dataStorageLocation;
      name_ = name;
      tileOverlapX_ = tileOverlapX;
      tileOverlapY_ = tileOverlapY;
      maxResLevel_ = maxResLevel;
      savingQueueSize_ = savingQueueSize;
   }

   public void initialize(Acquisition acq, JSONObject summaryMetadata) {
      acq_ =  acq;

      if (storeData_) {
         if (xyTiled_) {
            //tiled datasets have a fixed, acquisition-wide image size
            AcqEngMetadata.setWidth(summaryMetadata, (int) Engine.getCore().getImageWidth());
            AcqEngMetadata.setHeight(summaryMetadata, (int) Engine.getCore().getImageHeight());
         }

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

   public NDTiffAPI getStorage() {
      return storage_;
   }

   private void createDisplay(JSONObject summaryMetadata) {
      //create display
      displayCommunicationExecutor_ = Executors.newSingleThreadExecutor((Runnable r)
              -> new Thread(r, "Image viewer communication thread"));

      viewer_ = new NDViewer(this, (ViewerAcquisitionInterface) acq_,
              summaryMetadata, AcqEngMetadata.getPixelSizeUm(summaryMetadata), AcqEngMetadata.isRGB(summaryMetadata));

      viewer_.setWindowTitle(name_ + (acq_ != null
              ? (acq_.areEventsFinished()? " (Finished)" : " (Running)") : " (Loaded)"));
      //add functions so display knows how to parse time and z infomration from image tags
      viewer_.setReadTimeMetadataFunction((JSONObject tags) -> AcqEngMetadata.getElapsedTimeMs(tags));
      viewer_.setReadZMetadataFunction((JSONObject tags) -> AcqEngMetadata.getStageZIntended(tags));
   }

   public void putImage(final TaggedImage taggedImg) {
      HashMap<String, Integer> axes = AcqEngMetadata.getAxes(taggedImg.tags);
      final Future added;
      if (xyTiled_) {
         //Convert event row/col to image row/col
         axes.put(AcqEngMetadata.AXES_GRID_COL , AcqEngMetadata.getGridCol(taggedImg.tags));
         axes.put(AcqEngMetadata.AXES_GRID_ROW , AcqEngMetadata.getGridRow(taggedImg.tags));

         added = storage_.putImageMultiRes(taggedImg.pix, taggedImg.tags, axes,
                 AcqEngMetadata.isRGB(taggedImg.tags),
                 AcqEngMetadata.getHeight(taggedImg.tags),
                 AcqEngMetadata.getWidth(taggedImg.tags));
      } else {
         added = null;
         storage_.putImage(taggedImg.pix, taggedImg.tags, axes,
                 AcqEngMetadata.isRGB(taggedImg.tags),
                 AcqEngMetadata.getHeight(taggedImg.tags),
                 AcqEngMetadata.getWidth(taggedImg.tags));
      }


      if (showViewer_) {
         //Check if new viewer to init display settings
         String channelName = AcqEngMetadata.getChannelName(taggedImg.tags);
         boolean newChannel = !channelNames_.contains(channelName);
         if (newChannel) {
            channelNames_.add(channelName);
         }

         //put on different thread to not slow down acquisition
         displayCommunicationExecutor_.submit(new Runnable() {
            @Override
            public void run() {
               try {
                  if (added != null) {
                     added.get(); //needed to make sure multi res data at higher resolutions kept up to date
                  }
               } catch (Exception e) {
                  Engine.getCore().logMessage(e.getMessage());
                  throw new RuntimeException(e);
               }
               if (newChannel) {
                  //Insert a preferred color. Make a copy just in case concurrency issues
                  String chName = AcqEngMetadata.getChannelName(taggedImg.tags);
//                  Color c = Color.white; //TODO could add color memory here (or maybe viewer already handles it...)
                  int bitDepth = AcqEngMetadata.getBitDepth(taggedImg.tags);
                  viewer_.setChannelDisplaySettings(chName, null, bitDepth);
               }
               HashMap<String, Integer> axes = AcqEngMetadata.getAxes(taggedImg.tags);
               if (xyTiled_) {
                  //remove this so the viewer doesn't show it
                  axes.remove(AcqEngMetadata.AXES_GRID_ROW);
                  axes.remove(AcqEngMetadata.AXES_GRID_COL);
               }
               viewer_.newImageArrived(axes, AcqEngMetadata.getChannelName(taggedImg.tags));
            }
         });
      }
   }
  
   ///////// Data source interface for Viewer //////////
   @Override
   public int[] getBounds() {
      return storage_.getImageBounds();
   }

   @Override
   public TaggedImage getImageForDisplay(HashMap<String, Integer> axes, int resolutionindex,
           double xOffset, double yOffset, int imageWidth, int imageHeight) {

      return storage_.getDisplayImage(
              axes, resolutionindex, (int) xOffset, (int) yOffset,
              imageWidth, imageHeight);
   }

   @Override
   public Set<HashMap<String, Integer>> getStoredAxes() {
      return storage_.getAxesSet();
   }

   @Override
   public int getMaxResolutionIndex() {
      return storage_.getNumResLevels() - 1;
   }

   @Override
   public String getDiskLocation() {
      return dir_;
   }
   
   public void close() {
      storage_.close();
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
         viewer_.setWindowTitle(name_ + " (Finished)");
         displayCommunicationExecutor_.shutdown();
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

   boolean isXYTiled() {
      return xyTiled_;
   }

   int getOverlapX() {
      return tileOverlapX_;
   }

   int getOverlapY() {
      return tileOverlapY_;
   }
}
