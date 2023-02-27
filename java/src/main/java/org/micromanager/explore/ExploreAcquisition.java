///////////////////////////////////////////////////////////////////////////////
// AUTHOR:       Henry Pinkard, henry.pinkard@gmail.com
//
// COPYRIGHT:    University of California, San Francisco, 2015
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
//

package org.micromanager.explore;

import java.awt.geom.Point2D;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.stream.Stream;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.internal.Engine;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.main.AcquisitionEvent;
import org.micromanager.acqj.main.XYTiledAcquisition;
import org.micromanager.acqj.util.AcqEventModules;
import org.micromanager.acqj.util.AcquisitionEventIterator;
import org.micromanager.acqj.util.ChannelSetting;
import org.micromanager.acqj.util.xytiling.XYStagePosition;
import org.micromanager.explore.gui.ChannelGroupSettings;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.NDViewerAPI;
import org.micromanager.ndviewer.api.NDViewerAcqInterface;
import org.micromanager.remote.PycroManagerCompatibleAcq;

/**
 * A single time point acquisition that can dynamically expand in X,Y, and Z.
 *
 * @author Henry
 */
public class ExploreAcquisition extends XYTiledAcquisition
        implements PycroManagerCompatibleAcq, NDViewerAcqInterface, ZAcquisitionInterface {

   private boolean started_ = false;
   private volatile double zTop_;
   private volatile double zBottom_;
   private List<XYStagePosition> positions_;

   //Map with slice index as keys used to get rid of duplicate events
   private ConcurrentHashMap<Integer, LinkedBlockingQueue<ExploreTileWaitingToAcquire>>
         queuedTileEvents_ = new ConcurrentHashMap<>();

   private ExecutorService submittedSequenceMonitorExecutor_ =
         Executors.newSingleThreadExecutor((Runnable r) -> {
            return new Thread(r, "Submitted sequence monitor");
         });

   private String zStage_;

   private final double zOrigin_;
   private final double zStep_;
   private int minSliceIndex_;
   private int maxSliceIndex_;
   private Consumer<String> logger_;
   ChannelGroupSettings channels_;

   public ExploreAcquisition(int pixelOverlapX, int pixelOverlapY, double ZStep, ChannelGroupSettings channels,
                             XYTiledAcqViewerStorageAdapater adapter,
                             Consumer<String> logger) {
      super(adapter,
              pixelOverlapX, pixelOverlapY,
              // Add metadata specific to Magellan explore
              new Consumer<JSONObject>() {
                 @Override
                 public void accept(JSONObject summaryMetadata) {
                    AcqEngMetadata.setExploreAcq(summaryMetadata, true);
                    AcqEngMetadata.setZStepUm(summaryMetadata, ZStep);
                 }
              });
      logger_ = logger;
      zStep_ = ZStep;
      channels_ = channels;
      try {
         zStage_ = Engine.getCore().getFocusDevice();
         //start at current z position
         zTop_ = Engine.getCore().getPosition(zStage_);
         zOrigin_ = zTop_;
         zBottom_ = Engine.getCore().getPosition(zStage_);
      } catch (Exception ex) {
         logger.accept("Couldn't get focus device position");
         throw new RuntimeException();
      }
      createXYPositions();
   }

   public double getZOrigin() {
      return zOrigin_;
   }

   public double getZStep() {
      return zStep_;
   }

   @Override
   public boolean isFinished() {
      return areEventsFinished() && getDataSink().isFinished();
   }

   @Override
   public void abort() {
      super.abort();
      submittedSequenceMonitorExecutor_.shutdownNow();
   }

   @Override
   public void start() {
      super.start();
      started_ = true;
   }



   /**
    * Submit a iterator of acquisition events for execution.
    *
    * @param iter an iterator of acquisition events
    * @return
    */
   public Future submitEventIterator(Iterator<AcquisitionEvent> iter) {
      return submittedSequenceMonitorExecutor_.submit(() -> {
         Future iteratorFuture = null;
         try {
            iteratorFuture = Engine.getInstance().submitEventIterator(iter);
            iteratorFuture.get();
         } catch (InterruptedException ex) {
            iteratorFuture.cancel(true);
         } catch (ExecutionException ex) {
           ex.printStackTrace();
            logger_.accept(ex.getMessage());
         }
      });

   }


   private void createXYPositions() {
      try {
         positions_ = new ArrayList<XYStagePosition>();
         positions_.add(new XYStagePosition(new Point2D.Double(Engine.getCore().getXPosition(),
                 Engine.getCore().getYPosition()), 0, 0));

      } catch (Exception e) {
         e.printStackTrace();
         logger_.accept("Problem with Acquisition's XY positions. Check acquisition settings");
         throw new RuntimeException();
      }
   }

   /**
    *
    * @param sliceIndex 0 based slice index
    * @return
    */
   public LinkedBlockingQueue<ExploreTileWaitingToAcquire>
            getTilesWaitingToAcquireAtSlice(int sliceIndex) {
      return queuedTileEvents_.get(sliceIndex);
   }

   public void acquireTileAtCurrentLocation() {
      double xPos;
      double yPos;
      double zPos;

      try {
         //get current XY and Z Positions
         zPos = Engine.getCore().getPosition(Engine.getCore().getFocusDevice());
         xPos = Engine.getCore().getXPosition();
         yPos = Engine.getCore().getYPosition();
      } catch (Exception ex) {
         logger_.accept("Couldnt get device positions from core");
         return;
      }

      int sliceIndex = (int) Math.round((zPos - zOrigin_) / zStep_);
      int posIndex = ((XYTiledAcqViewerStorageAdapater) getDataSink())
            .getFullResPositionIndexFromStageCoords(xPos, yPos);

      submitEvents(new int[]{(int) ((XYTiledAcqViewerStorageAdapater) getDataSink())
                  .getXYPosition(posIndex).getGridRow()},
              new int[]{(int) ((XYTiledAcqViewerStorageAdapater) getDataSink())
                    .getXYPosition(posIndex).getGridCol()}, sliceIndex, sliceIndex);
   }

   public void acquireTiles(final int r1, final int c1, final int r2, final int c2) {
      //So it doesnt slow down GUI
      new Thread(() -> {
         int minZIndex = getZLimitMinSliceIndex();
         int maxZIndex = getZLimitMaxSliceIndex();

         //order tile indices properly
         int row1 = Math.min(r1, r2);
         int row2 = Math.max(r1, r2);
         int col1 = Math.min(c1, c2);
         int col2 = Math.max(c1, c2);
         //Get position Indices from manager based on row and column
         //it will create new metadata as needed
         int[] newPositionRows = new int[(row2 - row1 + 1) * (col2 - col1 + 1)];
         int[] newPositionCols = new int[(row2 - row1 + 1) * (col2 - col1 + 1)];
         for (int r = row1; r <= row2; r++) {
            for (int c = col1; c <= col2; c++) {
               int relativeRow = (r - row1);
               int relativeCol = (c - col1);
               int numRows = (1 + row2 - row1);
               int i = ((relativeCol % 2 == 0) ? relativeRow : (numRows - relativeRow - 1))
                     + numRows * relativeCol;
               newPositionRows[i] = r;
               newPositionCols[i] = c;
            }
         }
         submitEvents(newPositionRows, newPositionCols, minZIndex, maxZIndex);

      }).start();

   }

   private void submitEvents(int[] newPositionRows, int[] newPositionCols, int minZIndex,
                             int maxZIndex) {
      int[] posIndices = getPixelStageTranslator()
              .getPositionIndices(newPositionRows, newPositionCols);
      List<XYStagePosition> allPositions = getPixelStageTranslator().getPositionList();
      List<XYStagePosition> selectedXYPositions = new ArrayList<XYStagePosition>();
      for (int i : posIndices) {
         selectedXYPositions.add(allPositions.get(i));
      }
      ArrayList<Function<AcquisitionEvent, Iterator<AcquisitionEvent>>> acqFunctions
              = new ArrayList<Function<AcquisitionEvent, Iterator<AcquisitionEvent>>>();
      acqFunctions.add(positions(selectedXYPositions));
      acqFunctions.add(AcqEventModules.zStack(minZIndex, maxZIndex + 1, zStep_, zOrigin_));
      if (channels_ != null && channels_.getNumChannels() > 0) {
         ArrayList<ChannelSetting> channels = new ArrayList<ChannelSetting>();
            for (String name : channels_.getChannelNames()) {
               if (channels_.getChannelSetting(name).use_) {
                  channels.add(channels_.getChannelSetting(name));
               }

         }
         acqFunctions.add(AcqEventModules.channels(channels));
      }

      Iterator<AcquisitionEvent> iterator = new AcquisitionEventIterator(
              new AcquisitionEvent(this), acqFunctions, monitorSliceIndices());

      //Get rid of duplicates, send to acquisition engine 
      Predicate<AcquisitionEvent> predicate = filterExistingEventsAndDisplayQueuedTiles();
      List<AcquisitionEvent> eventList = new LinkedList<AcquisitionEvent>();
      while (iterator.hasNext()) {
         AcquisitionEvent event = iterator.next();
         if (predicate.test(event)) {
            eventList.add(event);
         }
      }

      Function<AcquisitionEvent, AcquisitionEvent> removeTileToAcquireFn = (AcquisitionEvent e) -> {
         queuedTileEvents_.get(e.getZIndex()).remove(new ExploreTileWaitingToAcquire(e.getGridRow(),
                 e.getGridCol(), e.getZIndex(), e.getConfigPreset()));
         return e;
      };

      ArrayList<Function<AcquisitionEvent, Iterator<AcquisitionEvent>>> list
              = new ArrayList<Function<AcquisitionEvent, Iterator<AcquisitionEvent>>>();
      Function<AcquisitionEvent, Iterator<AcquisitionEvent>> fn = (AcquisitionEvent t) -> {
         return eventList.iterator();
      };
      list.add(fn);

      submitEventIterator(new AcquisitionEventIterator(null, list,
            removeTileToAcquireFn));
   }

   private Function<AcquisitionEvent, Iterator<AcquisitionEvent>>
            positions(List<XYStagePosition> positions) {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         if (positions == null) {
            builder.accept(event);
         } else {
            for (int index = 0; index < positions.size(); index++) {
               AcquisitionEvent posEvent = event.copy();
               //These tell it what to acquire
               posEvent.setGridCol(positions.get(index).getGridCol());
               posEvent.setGridRow(positions.get(index).getGridRow());
               //These tell how to store it
               posEvent.setAxisPosition(AcqEngMetadata.AXES_GRID_ROW, positions.get(index)
                     .getGridRow());
               posEvent.setAxisPosition(AcqEngMetadata.AXES_GRID_COL, positions.get(index)
                     .getGridCol());
               posEvent.setX(positions.get(index).getCenter().x);
               posEvent.setY(positions.get(index).getCenter().y);
               builder.accept(posEvent);
            }
         }
         return builder.build().iterator();
      };
   }

   private Predicate<AcquisitionEvent> filterExistingEventsAndDisplayQueuedTiles() {
      return (AcquisitionEvent event) -> {
         try {
            //add tile tile to list waiting to acquire for drawing purposes
            if (!queuedTileEvents_.containsKey(event.getZIndex())) {
               queuedTileEvents_.put(event.getZIndex(),
                     new LinkedBlockingQueue<ExploreTileWaitingToAcquire>());
            }

            ExploreTileWaitingToAcquire tile = new ExploreTileWaitingToAcquire(event.getGridRow(),
                    event.getGridCol(), event.getZIndex(), event.getConfigPreset());
            if (queuedTileEvents_.get(event.getZIndex()).contains(tile)) {
               return false; //This tile is already waiting to be acquired
            }
            queuedTileEvents_.get(event.getZIndex()).put(tile);
            return true;
         } catch (InterruptedException ex) {
            throw new RuntimeException(ex);
         }
      };

   }

   private Function<AcquisitionEvent, AcquisitionEvent> monitorSliceIndices() {
      return (AcquisitionEvent event) -> {
         minSliceIndex_ = Math.min(minSliceIndex_, getZLimitMinSliceIndex());
         maxSliceIndex_ = Math.max(maxSliceIndex_, getZLimitMaxSliceIndex());
         return event;
      };
   }

   /**
    * get min slice index for according to z limit sliders.
    *
    * @return
    */
   private int getZLimitMinSliceIndex() {
      return (int) Math.round((zTop_ - zOrigin_) / zStep_);
   }

   /**
    * get max slice index for current settings in explore acquisition.
    */
   private int getZLimitMaxSliceIndex() {
      return (int) Math.round((zBottom_ - zOrigin_) / zStep_);
   }

   /**
    * get z coordinate for slice position.
    */
   private double getZCoordinate(int sliceIndex) {
      return zOrigin_ + zStep_ * sliceIndex;
   }

   public void setZLimits(double zTop, double zBottom) {
      //Convention: z top should always be lower than zBottom
      zBottom_ = Math.max(zTop, zBottom);
      zTop_ = Math.min(zTop, zBottom);
   }

   @Override
   public NDTiffAPI getStorage() {
      return ((XYTiledAcqViewerStorageAdapater) dataSink_).getStorage();
   }

   @Override
   public int getEventPort() {
      return -1;
   }

   @Override
   public NDViewerAPI getViewer() {
      return ((XYTiledAcqViewerStorageAdapater) dataSink_).getViewer();
   }

   //slice and row/col index of an acquisition event in the queue
   public class ExploreTileWaitingToAcquire {

      public long row;
      public long col;
      public long sliceIndex;
      public String channelName = null;

      public ExploreTileWaitingToAcquire(long r, long c, int z, String ch) {
         row = r;
         col = c;
         sliceIndex = z;
         channelName = ch;
      }

      @Override
      public boolean equals(Object other) {
         String otherChannel = ((ExploreTileWaitingToAcquire) other).channelName;
         if (((ExploreTileWaitingToAcquire) other).col
               == col && ((ExploreTileWaitingToAcquire) other).row == row
                 && ((ExploreTileWaitingToAcquire) other).sliceIndex == sliceIndex) {
            if (otherChannel == null && channelName == null) {
               return true;
            }
            return otherChannel.equals(channelName);
         }
         return false;
      }

   }
}

