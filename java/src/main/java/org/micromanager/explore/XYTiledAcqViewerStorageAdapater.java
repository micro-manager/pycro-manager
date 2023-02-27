///////////////////////////////////////////////////////////////////////////////
//FILE:          MMImageCache.java
//PROJECT:       Micro-Manager
//SUBSYSTEM:     mmstudio
//-----------------------------------------------------------------------------
//
// AUTHOR:       Arthur Edelstein
// COPYRIGHT:    University of California, San Francisco, 2010
//
// LICENSE:      This file is distributed under the BSD license.
//               License text is included with the source distribution.
//
//               This file is distributed in the hope that it will be useful,
//               but WITHOUT ANY WARRANTY; without even the implied warranty
//               of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
//               IN NO EVENT SHALL THE COPYRIGHT OWNER OR
//               CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
//               INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES.

package org.micromanager.explore;

import java.awt.Point;
import java.awt.geom.Point2D;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedList;
import java.util.Set;
//import java.util.concurrent.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.DoubleStream;
import javax.swing.SwingUtilities;
import mmcorej.TaggedImage;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.api.DataSink;
import org.micromanager.acqj.internal.Engine;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.main.XYTiledAcquisition;
import org.micromanager.acqj.util.xytiling.PixelStageTranslator;
import org.micromanager.acqj.util.xytiling.XYStagePosition;
import org.micromanager.explore.gui.ChannelGroupSettings;
import org.micromanager.explore.gui.ExploreControlsPanel;
import org.micromanager.explore.gui.ExploreMouseListener;
import org.micromanager.ndtiffstorage.MultiresNDTiffAPI;
import org.micromanager.ndtiffstorage.NDTiffStorage;
import org.micromanager.ndviewer.api.DataSourceInterface;
import org.micromanager.ndviewer.api.OverlayerPlugin;
import org.micromanager.ndviewer.api.NDViewerAcqInterface;
import org.micromanager.ndviewer.api.NDViewerAPI;
import org.micromanager.ndviewer.main.NDViewer;
import org.micromanager.ndviewer.overlay.Overlay;

/**
 * Created by magellan acquisition to manage viewer, data storage, and
 * conversion between pixel coordinate space (which the viewer and storage work
 * in) and the stage coordiante space (which the acquisition works in).
 */
public class XYTiledAcqViewerStorageAdapater implements DataSink, DataSourceInterface {

   private static final int SAVING_QUEUE_SIZE = 30;

   protected MultiresNDTiffAPI storage_;
   private ExecutorService displayCommunicationExecutor_;
   public final boolean loadedData_;
   private String dir_;
   private String name_;
   private final boolean showDisplay_;
   protected NDViewer display_;
   private JSONObject summaryMetadata_;
   private CopyOnWriteArrayList<String> channelNames_ = new CopyOnWriteArrayList<String>();
   private LinkedList<Consumer<HashMap<String, Object>>> displayUpdateOnImageHooks_
           = new LinkedList<Consumer<HashMap<String, Object>>>();

   private OverlayerPlugin overlayer_;
   protected double pixelSizeZ_;
   protected double zOrigin_;

   protected ZAcquisitionInterface acq_;
   ExploreMouseListener mouseListener_;
   private Consumer<String> logger_;
   public final boolean explore_;
   private ChannelGroupSettings channels_;

   public XYTiledAcqViewerStorageAdapater(String dir, String name, boolean showDisplay,
                                          boolean exploreUI, ChannelGroupSettings exploreChannels, Consumer<String> logger) {
      displayCommunicationExecutor_ = Executors.newSingleThreadExecutor((Runnable r)
              -> new Thread(r, "Magellan viewer communication thread"));
      logger_ = logger;
      dir_ = dir;
      name_ = name;
      loadedData_ = false;
      showDisplay_ = showDisplay;
      explore_ = exploreUI;
      if (explore_) {
         channels_ = exploreChannels;
      }
   }

   //Constructor for opening loaded data
   public XYTiledAcqViewerStorageAdapater(String dir, Consumer<String> logger) throws IOException {
      logger_ = logger;
      displayCommunicationExecutor_ = Executors.newSingleThreadExecutor((Runnable r)
              -> new Thread(r, "Magellan viewer communication thread"));
      storage_ = new NDTiffStorage(dir);
      dir_ = dir;
      loadedData_ = true;
      showDisplay_ = true;
      summaryMetadata_ = storage_.getSummaryMetadata();
      explore_ = false;
      createDisplay();
   }
   public NDViewerAPI getViewer() {
      return display_;
   }

   @Override
   public void initialize(Acquisition acq, JSONObject summaryMetadata) {
      acq_ = (ZAcquisitionInterface) acq;

      pixelSizeZ_ = acq_.getZStep();
      zOrigin_ =  acq_.getZOrigin();

      summaryMetadata_ = summaryMetadata;

      AcqEngMetadata.setHeight(summaryMetadata, (int) Engine.getCore().getImageHeight());
      AcqEngMetadata.setWidth(summaryMetadata, (int) Engine.getCore().getImageWidth());

      storage_ = new NDTiffStorage(dir_, name_,
                 summaryMetadata,
                 AcqEngMetadata.getPixelOverlapX(summaryMetadata),
                 AcqEngMetadata.getPixelOverlapY(summaryMetadata),
                 true, null, SAVING_QUEUE_SIZE,
                Engine.getCore().debugLogEnabled() ? (Consumer<String>) s
                      -> Engine.getCore().logMessage(s) : null, true);

      boolean addExploreControls = true;
      if (showDisplay_) {
         createDisplay();
      }
      //storage class has determined unique acq name, so it can now be stored
      name_ = this.getUniqueAcqName();
   }

   public MultiresNDTiffAPI getStorage() {
      return storage_;
   }




   private void moveViewToVisibleArea() {
      //check for valid tiles (at lowest res) at this slice
      Set<Point> tiles = getTileIndicesWithDataAt(
              (Integer) display_.getAxisPosition(AcqEngMetadata.Z_AXIS));
      if (tiles.size() == 0) {
         return;
      }
      // center of one tile must be within corners of current view
      double minDistance = Integer.MAX_VALUE;
      //do all calculations at full resolution
      long currentX = (long) display_.getViewOffset().x;
      long currentY = (long) display_.getViewOffset().y;

      //Check if any point is visible, if so return
      for (Point p : tiles) {
         //calclcate limits on margin of tile that must remain in view
         long tileX1 = (long) ((0.1 + p.x) * getDisplayTileWidth());
         long tileX2 = (long) ((0.9 + p.x) * getDisplayTileWidth());
         long tileY1 = (long) ((0.1 + p.y) * getDisplayTileHeight());
         long tileY2 = (long) ((0.9 + p.y) * getDisplayTileHeight());
         //get bounds of viewing area
         long fovX1 = (long) display_.getViewOffset().x;
         long fovY1 = (long) display_.getViewOffset().y;
         long fovX2 = (long) (fovX1 + display_.getFullResSourceDataSize().x);
         long fovY2 = (long) (fovY1 + display_.getFullResSourceDataSize().y);

         //check if tile and fov intersect
         boolean xInView = fovX1 < tileX2 && fovX2 > tileX1;
         boolean yInView = fovY1 < tileY2 && fovY2 > tileY1;
         boolean intersection = xInView && yInView;

         if (intersection) {
            return; //at least one tile is in view, don't need to do anything
         }
      }

      //Go through all tiles and find minium move to reset visible criteria
      ArrayList<Point2D.Double> newPos = new ArrayList<Point2D.Double>();
      for (Point p : tiles) {
         //do all calculations at full resolution
         currentX = (long) display_.getViewOffset().x;
         currentY = (long) display_.getViewOffset().y;

         //calclcate limits on margin of tile that must remain in view
         long tileX1 = (long) ((0.1 + p.x) * getDisplayTileWidth());
         long tileX2 = (long) ((0.9 + p.x) * getDisplayTileWidth());
         long tileY1 = (long) ((0.1 + p.y) * getDisplayTileHeight());
         long tileY2 = (long) ((0.9 + p.y) * getDisplayTileHeight());
         //get bounds of viewing area
         long fovX1 = (long) display_.getViewOffset().x;
         long fovY1 = (long) display_.getViewOffset().y;
         long fovX2 = (long) (fovX1 + display_.getFullResSourceDataSize().x);
         long fovY2 = (long) (fovY1 + display_.getFullResSourceDataSize().y);

         //check if tile and fov intersect
         boolean xInView = fovX1 < tileX2 && fovX2 > tileX1;
         boolean yInView = fovY1 < tileY2 && fovY2 > tileY1;

         //tile to fov corner to corner distances
         double tl = ((tileX1 - fovX2) * (tileX1 - fovX2) + (tileY1 - fovY2)
                 * (tileY1 - fovY2)); //top left tile, botom right fov
         double tr = ((tileX2 - fovX1) * (tileX2 - fovX1) + (tileY1 - fovY2)
                 * (tileY1 - fovY2)); // top right tile, bottom left fov
         double bl = ((tileX1 - fovX2) * (tileX1 - fovX2) + (tileY2 - fovY1)
                 * (tileY2 - fovY1)); // bottom left tile, top right fov
         double br = ((tileX1 - fovX1) * (tileX1 - fovX1) + (tileY2 - fovY1)
                 * (tileY2 - fovY1)); //bottom right tile, top left fov

         double closestCornerDistance = Math.min(Math.min(tl, tr), Math.min(bl, br));
         if (closestCornerDistance < minDistance) {
            minDistance = closestCornerDistance;
            long newX;
            long newY;
            if (tl <= tr && tl <= bl && tl <= br) { //top left tile, botom right fov
               newX = (long) (xInView ? currentX : tileX1 - display_.getFullResSourceDataSize().x);
               newY = (long) (yInView ? currentY : tileY1 - display_.getFullResSourceDataSize().y);
            } else if (tr <= tl && tr <= bl && tr <= br) { // top right tile, bottom left fov
               newX = xInView ? currentX : tileX2;
               newY = (long) (yInView ? currentY : tileY1 - display_.getFullResSourceDataSize().y);
            } else if (bl <= tl && bl <= tr && bl <= br) { // bottom left tile, top right fov
               newX = (long) (xInView ? currentX : tileX1 - display_.getFullResSourceDataSize().x);
               newY = yInView ? currentY : tileY2;
            } else { //bottom right tile, top left fov
               newX = xInView ? currentX : tileX2;
               newY = yInView ? currentY : tileY2;
            }
            newPos.add(new Point2D.Double(newX, newY));
         }
      }

      long finalCurrentX = currentX;
      long finalCurrentY = currentY;
      DoubleStream dists = newPos.stream().mapToDouble(value -> Math.pow(value.x - finalCurrentX, 2)
              + Math.pow(value.y - finalCurrentY, 2));

      double minDist = dists.min().getAsDouble();
      Point2D.Double newPoint =  newPos.stream().filter(
              value -> (Math.pow(value.x - finalCurrentX, 2)
                      + Math.pow(value.y - finalCurrentY, 2))
                      == minDist).collect(Collectors.toList()).get(0);

      display_.setViewOffset(newPoint.x, newPoint.y);
   }

   public LinkedBlockingQueue<ExploreAcquisition.ExploreTileWaitingToAcquire>
   getTilesWaitingToAcquireAtVisibleSlice() {
      return ((ExploreAcquisition) acq_).getTilesWaitingToAcquireAtSlice(
              (Integer) display_.getAxisPosition(AcqEngMetadata.Z_AXIS));
   }

   public Point getTileIndicesFromDisplayedPixel(int x, int y) {
      double scale = display_.getMagnification();
      int fullResX = (int) ((x / scale) + display_.getViewOffset().x);
      int fullResY = (int) ((y / scale) + display_.getViewOffset().y);
      int xTileIndex = fullResX / getDisplayTileWidth() - (fullResX >= 0 ? 0 : 1);
      int yTileIndex = fullResY / getDisplayTileHeight() - (fullResY >= 0 ? 0 : 1);
      return new Point(xTileIndex, yTileIndex);
   }

   /**
    * return the pixel location in coordinates at appropriate res level of the
    * top left pixel for the given row/column
    *
    * @param row
    * @param col
    * @return
    */
   public Point getDisplayedPixel(long row, long col) {
      double scale = display_.getMagnification();
      int x = (int) ((col * getDisplayTileWidth() - display_.getViewOffset().x) * scale);
      int y = (int) ((row * getDisplayTileHeight() - display_.getViewOffset().y) * scale);
      return new Point(x, y);
   }

   //OVerride zoom and pan to restrain viewer to explored region in explore acqs
   public void pan(int dx, int dy) {
      display_.pan(dx, dy);
      if (getBounds() == null) {
         moveViewToVisibleArea();
         display_.update();
      }
   }

   public void zoom(double factor, Point mouseLocation) {
      display_.zoom(factor, mouseLocation);
      if (getBounds() == null) {
         moveViewToVisibleArea();
         display_.update();
      }
   }




   private void createDisplay() {
      //create display
      try {

         display_ = new NDViewer(this, (NDViewerAcqInterface) acq_, summaryMetadata_, AcqEngMetadata.getPixelSizeUm(summaryMetadata_),
                 AcqEngMetadata.isRGB(summaryMetadata_));

         display_.setWindowTitle(getUniqueAcqName() + (acq_ != null
                 ? (((NDViewerAcqInterface) acq_).isFinished() ? " (Finished)" : " (Running)") : " (Loaded)"));
         //add functions so display knows how to parse time and z infomration from image tags
         display_.setReadTimeMetadataFunction((JSONObject tags)
               -> AcqEngMetadata.getElapsedTimeMs(tags));
         display_.setReadZMetadataFunction((JSONObject tags)
               -> AcqEngMetadata.getStageZIntended(tags));

         //add mouse listener for the canvas
         if (explore_) {
            mouseListener_ = new ExploreMouseListener(this, (ExploreAcquisition) acq_, display_, logger_);
            //add overlayer
            overlayer_ = new ExploreOverlayer(this, mouseListener_);
            display_.setOverlayerPlugin(overlayer_);

            ExploreControlsPanel exploreControls = new ExploreControlsPanel(this,
                    (ExploreOverlayer) overlayer_, channels_);
            display_.addControlPanel(exploreControls);

            display_.setCustomCanvasMouseListener(mouseListener_);




            if (explore_) {
               display_.addSetImageHook(new Consumer<HashMap<String, Object>>() {
                  @Override
                  public void accept(HashMap<String, Object> axes) {
                     if (axes.containsKey(AcqEngMetadata.Z_AXIS)) {
                        Integer i = (Integer) axes.get(AcqEngMetadata.Z_AXIS);
                        exploreControls.updateControls(i);
                     }
                  }
               });
            }
         }


      } catch (Exception e) {
         e.printStackTrace();
         logger_.accept("Couldn't create display succesfully");
      }
   }

   public void putImage(final TaggedImage taggedImg) {

      String channelName = (String) AcqEngMetadata.getAxes(taggedImg.tags).get("channel");
      boolean newChannel = !channelNames_.contains(channelName);
      if (newChannel) {
         channelNames_.add(channelName);
      }
      HashMap<String, Object> axes = AcqEngMetadata.getAxes(taggedImg.tags);
      Future added = storage_.putImageMultiRes(taggedImg.pix, taggedImg.tags, axes,
              AcqEngMetadata.isRGB(taggedImg.tags), AcqEngMetadata.getBitDepth(taggedImg.tags),
              AcqEngMetadata.getHeight(taggedImg.tags), AcqEngMetadata.getWidth(taggedImg.tags));

      if (showDisplay_) {
         //put on different thread to not slow down acquisition

         displayCommunicationExecutor_.submit(new Runnable() {
            @Override
            public void run() {
               try {
                  added.get();


                  HashMap<String, Object> axes = AcqEngMetadata.getAxes(taggedImg.tags);
                  //Display doesn't know about these in tiled layout
                  axes.remove(AcqEngMetadata.AXES_GRID_ROW);
                  axes.remove(AcqEngMetadata.AXES_GRID_COL);
                  //  String channelName = MagellanMD.getChannelName(taggedImg.tags);
                  display_.newImageArrived(axes);

                  for (Consumer<HashMap<String, Object>> displayHook : displayUpdateOnImageHooks_) {
                     displayHook.accept(axes);
                  }


               } catch (Exception e) {
                  e.printStackTrace();;
                  throw new RuntimeException(e);
               }
            }
         });
      }
   }


   /**
    * Called when images done arriving.
    */
   public void finish() {
      if (!storage_.isFinished()) {
         //Get most up to date display settings
         JSONObject displaySettings = display_.getDisplaySettingsJSON();
         storage_.setDisplaySettings(displaySettings);
         storage_.finishedWriting();
      }
      display_.setWindowTitle(getUniqueAcqName() + " (Finished)");
      displayCommunicationExecutor_.shutdown();
      displayCommunicationExecutor_ = null;
   }

   public boolean isFinished() {
      return storage_ == null ? true : storage_.isFinished();
   }

   public String getDiskLocation() {
      return storage_.getDiskLocation();
   }

   /**
    * Used for data loaded from disk.
    *
    * @return
    */
   public JSONObject getDisplayJSON() {
      try {
         return storage_.getDisplaySettings() == null ? null
               : new JSONObject(storage_.getDisplaySettings().toString());
      } catch (JSONException ex) {
         throw new RuntimeException("THis shouldnt happen");
      }
   }

   /**
    * The display calls this when its closing.
    */
   @Override
   public void close() {
      if (storage_.isFinished()) {

         storage_.close();
         storage_ = null;
         displayUpdateOnImageHooks_ = null;

         mouseListener_ = null;
         overlayer_ = null;
         display_ = null;

      } else {
         //keep resubmitting so that finish, which comes from a different thread, happens first
         SwingUtilities.invokeLater(new Runnable() {
            @Override
            public void run() {
               XYTiledAcqViewerStorageAdapater.this.close();
            }
         });
      }
   }

   @Override
   public int getImageBitDepth(HashMap<String, Object> axesPositions) {
      return storage_.getEssentialImageMetadata(axesPositions).bitDepth;
   }

   public JSONObject getSummaryMD() {
      if (storage_ == null) {
         logger_.accept("imageStorage_ is null in getSummaryMetadata");
         return null;
      }
      try {
         return new JSONObject(storage_.getSummaryMetadata().toString());
      } catch (JSONException ex) {
         throw new RuntimeException("This shouldnt happen");
      }
   }
   
   private PixelStageTranslator getPixelStageTranslator() {
      return ((XYTiledAcquisition) acq_).getPixelStageTranslator();
   }

   public int getDisplayTileHeight() {
      return getPixelStageTranslator() == null ? 0
            : getPixelStageTranslator().getDisplayTileHeight();
   }

   public int getDisplayTileWidth() {
      return getPixelStageTranslator() == null ? 0
            : getPixelStageTranslator().getDisplayTileWidth();
   }

   public boolean isExploreAcquisition() {
      return explore_;
   }

   public int[] getBounds() {
      if (isExploreAcquisition() && !loadedData_) {
         return null;
      }
      return storage_.getImageBounds();
   }

   @Override
   public TaggedImage getImageForDisplay(HashMap<String, Object> axes, int resolutionindex,
           double xOffset, double yOffset, int imageWidth, int imageHeight) {

      return storage_.getDisplayImage(
              axes,
              resolutionindex,
              (int) xOffset, (int) yOffset,
              imageWidth, imageHeight);
   }

   @Override
   public Set<HashMap<String, Object>> getImageKeys() {

      return storage_.getAxesSet().stream().map(
            new Function<HashMap<String, Object>, HashMap<String, Object>>() {
            @Override
            public HashMap<String, Object> apply(HashMap<String, Object> axes) {
               HashMap<String, Object> copy = new HashMap<String, Object>(axes);
               //delete row and column so viewer doesn't use them
               copy.remove(NDTiffStorage.ROW_AXIS);
               copy.remove(NDTiffStorage.COL_AXIS);
               return copy;
            }
         }).collect(Collectors.toSet());
   }

   public boolean anythingAcquired() {
      return storage_ == null || !storage_.getAxesSet().isEmpty();
   }

   public String getName() {
      return name_;
   }

   public String getDir() {
      return dir_;
   }

   public String getUniqueAcqName() {
      if (loadedData_) {
         return dir_;
      }
      File file = new File(storage_.getDiskLocation());
      String simpleFileName = file.getName();
      return simpleFileName;
   }

   public Point2D.Double stageCoordsFromPixelCoords(int x, int y) {
      return stageCoordsFromPixelCoords(x, y, display_.getMagnification(),
            display_.getViewOffset());
   }

   /**
    *
    * @param absoluteX x coordinate in the full Res stitched image
    * @param absoluteY y coordinate in the full res stitched image
    * @return stage coordinates of the given pixel position
    */
   public Point2D.Double stageCoordsFromPixelCoords(int absoluteX, int absoluteY,
           double mag, Point2D.Double offset) {
      long newX = (long) (absoluteX / mag + offset.x);
      long newY = (long) (absoluteY / mag + offset.y);
      return getPixelStageTranslator().getStageCoordsFromPixelCoords(newX, newY);
   }

   public int getFullResPositionIndexFromStageCoords(double xPos, double yPos) {
      return getPixelStageTranslator().getFullResPositionIndexFromStageCoords(xPos, yPos);
   }

   /* 
    * @param stageCoords x and y coordinates of image in stage space
    * @return absolute, full resolution pixel coordinate of given stage posiiton
    */
   public Point pixelCoordsFromStageCoords(double x, double y, double magnification,
           Point2D.Double offset) {
      Point fullResCoords = getPixelStageTranslator().getPixelCoordsFromStageCoords(x, y);
      return new Point(
              (int) ((fullResCoords.x - offset.x) * magnification),
              (int) ((fullResCoords.y - offset.y) * magnification));
   }

   public XYStagePosition getXYPosition(int posIndex) {
      return getPixelStageTranslator().getXYPosition(posIndex);
   }

   public int getMaxResolutionIndex() {
      return storage_.getNumResLevels() - 1;
   }

   public Set<Point> getTileIndicesWithDataAt(int zIndex) {
      return storage_.getTileIndicesWithDataAt(zIndex);
   }

   public double getZStep() {
      return pixelSizeZ_;
   }


   public void setOverlay(Overlay surfOverlay) {
      display_.setOverlay(surfOverlay);
   }

   public void acquireTileAtCurrentPosition() {
      ((ExploreAcquisition) acq_).acquireTileAtCurrentLocation();
   }

   public void setExploreZLimits(double zTop, double zBottom) {
      ((ExploreAcquisition) acq_).setZLimits(zTop, zBottom);
   }


   public Point2D.Double getStageCoordinateOfViewCenter() {
      return getPixelStageTranslator().getStageCoordsFromPixelCoords(
              (long) (display_.getViewOffset().x + display_.getFullResSourceDataSize().x / 2),
              (long) (display_.getViewOffset().y + display_.getFullResSourceDataSize().y / 2));

   }



   public void initializeViewerToLoaded(
           HashMap<String, Object> axisMins, HashMap<String, Object> axisMaxs) {

      LinkedList<String> channelNames = new LinkedList<String>();
      for (HashMap<String, Object> axes : storage_.getAxesSet()) {
         if (axes.containsKey(AcqEngMetadata.CHANNEL_AXIS)) {
            if (!channelNames.contains(axes.get(AcqEngMetadata.CHANNEL_AXIS))) {
               channelNames.add((String) axes.get(AcqEngMetadata.CHANNEL_AXIS));
            }
         }
      }
      display_.initializeViewerToLoaded(channelNames, storage_.getDisplaySettings(),
            axisMins, axisMaxs);
   }

   public Set<HashMap<String, Object>> getAxesSet() {
      return storage_.getAxesSet();
   }

   public Point2D.Double[] getDisplayTileCorners(XYStagePosition pos) {
      return getPixelStageTranslator().getDisplayTileCornerStageCoords(pos);
   }


   public double getZCoordinateOfDisplayedSlice() {
      int index = (Integer) display_.getAxisPosition(AcqEngMetadata.Z_AXIS);
      return index * getZStep() + zOrigin_;
   }

   public int zCoordinateToZIndex(double z) {
      return (int) ((z - zOrigin_) / pixelSizeZ_);
   }

   public ExploreMouseListener getExploreMouseListener() {
      if (explore_) {
         return mouseListener_;
      }
      return null;
   }
}
