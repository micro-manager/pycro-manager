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
package main.java.org.micromanager.plugins.magellan.acq;

import main.java.org.micromanager.plugins.magellan.imagedisplay.DisplayPlus;
import java.awt.Color;
import java.util.LinkedList;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import main.java.org.micromanager.plugins.magellan.channels.ChannelSpec;
import main.java.org.micromanager.plugins.magellan.coordinates.PositionManager;
import main.java.org.micromanager.plugins.magellan.json.JSONArray;
import main.java.org.micromanager.plugins.magellan.json.JSONObject;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import org.micromanager.PositionListManager;

/**
 * Abstract class that manages a generic acquisition. Subclassed into specific
 * types of acquisition
 */
public abstract class Acquisition {

   protected final double zStep_;
   protected double zOrigin_;
   protected volatile int minSliceIndex_ = 0, maxSliceIndex_ = 0;
   protected String xyStage_, zStage_;
   protected boolean zStageHasLimits_ = false;
   protected double zStageLowerLimit_, zStageUpperLimit_;
   protected AcquisitionEvent lastEvent_ = null;
   protected TaggedImageSaver imageSaver_;
   protected volatile boolean finished_ = false;
   private String name_;
   private long startTime_ms_ = -1;
   private int overlapX_, overlapY_;
   private volatile boolean pause_ = false;
   private Object pauseLock_ = new Object();
   protected ChannelSpec channels_;
   protected ExecutorService eventGenerator_;
   protected PositionManager posManager_;
   private MagellanEngine eng_;
   private LinkedBlockingDeque<Future<Future>> submittedEvents_ = new LinkedBlockingDeque<Future<Future>>();

   public Acquisition(double zStep, ChannelSpec channels) throws Exception {
      eng_ = MagellanEngine.getInstance();
      xyStage_ = Magellan.getCore().getXYStageDevice();
      zStage_ = Magellan.getCore().getFocusDevice();
      channels_ = channels;
      //"postion" is not generic name..and as of right now there is now way of getting generic z positions
      //from a z deviec in MM
      String positionName = "Position";
      if (Magellan.getCore().hasProperty(zStage_, positionName)) {
         zStageHasLimits_ = Magellan.getCore().hasPropertyLimits(zStage_, positionName);
         if (zStageHasLimits_) {
            zStageLowerLimit_ = Magellan.getCore().getPropertyLowerLimit(zStage_, positionName);
            zStageUpperLimit_ = Magellan.getCore().getPropertyUpperLimit(zStage_, positionName);
         }
      }
      zStep_ = zStep;
   }
   
   protected void initialize(String dir, String name, double overlapPercent) {
      overlapX_ = (int) (Magellan.getCore().getImageWidth() * overlapPercent / 100);
      overlapY_ = (int) (Magellan.getCore().getImageHeight() * overlapPercent / 100);
      JSONObject summaryMetadata = MagellanEngine.makeSummaryMD(this, name);
      MultiResMultipageTiffStorage imageStorage = new MultiResMultipageTiffStorage(dir, summaryMetadata);
      posManager_ = imageStorage.getPosManager();
      //storage class has determined unique acq name, so it can now be stored
      name_ = imageStorage.getUniqueAcqName();
      MMImageCache imageCache = new MMImageCache(imageStorage);
      imageCache.setSummaryMetadata(summaryMetadata);
      new DisplayPlus(imageCache, this, summaryMetadata, imageStorage);
      imageSaver_ = new TaggedImageSaver(imageCache, this);
      eventGenerator_ = Executors.newSingleThreadExecutor(new ThreadFactory() {
         @Override
         public Thread newThread(Runnable r) {
            return new Thread(r, name_ + ": Event generator");
         }
      });
   }
   
   protected void submitAcquisitionEvent(AcquisitionEvent event) {
      //submit and add future to a queueu of futures
      
      
   }
   
   public Future saveImage(MagellanTaggedImage image) {
      return imageSaver_.submit(image);
   }
   
   protected abstract JSONArray createInitialPositionList();


   public void abort() {
      //Do this on a seperate thread. Maybe this was to avoid deadlock?
      new Thread(new Runnable() {
         @Override
         public void run() {

            if (finished_) {
               //acq already aborted
               return;
            }

            if (Acquisition.this.isPaused()) {
               Acquisition.this.togglePaused();
            }
            eventGenerator_.shutdownNow();
            //wait for shutdown
            try {
               //wait for it to exit
               while (!eventGenerator_.awaitTermination(5, TimeUnit.MILLISECONDS)) {
               }
            } catch (InterruptedException ex) {
               Log.log("Unexpected interrupt while trying to abort acquisition", true);
               //shouldn't happen
            }
            //abort all pending events specific to this acquisition
            clearEvents();
            //signal acquisition engine to start finishing process
            Future<Future> endAcqFuture = eng_.submitEvent(AcquisitionEvent.createAcquisitionFinishedEvent(Acquisition.this));
            Future imageSaverDoneFuture;
            try {
               imageSaverDoneFuture = endAcqFuture.get();
               imageSaverDoneFuture.get();
            } catch (InterruptedException ex) {
               Log.log("aborting acquisition interrupted");
            } catch (ExecutionException ex) {
               Log.log("Exception encountered when trying to end acquisition", true);
            }
            //shouldnt need this but just in case
            imageSaver_.waitForShutdown();
         }
      }, "Aborting thread").start();
   }

   public String getXYStageName() {
      return xyStage_;
   }

   public String getZStageName() {
      return zStage_;
   }

   /**
    * indices are 1 based and positive
    *
    * @param sliceIndex -
    * @param frameIndex -
    * @return
    */
   public double getZCoordinateOfDisplaySlice(int displaySliceIndex) {
      displaySliceIndex += minSliceIndex_;
      return zOrigin_ + zStep_ * displaySliceIndex;
   }

   public int getDisplaySliceIndexFromZCoordinate(double z) {
      return (int) Math.round((z - zOrigin_) / zStep_) - minSliceIndex_;
   }

   /**
    * Return the maximum number of possible channels for the acquisition, not
    * all of which are neccessarily active
    *
    * @return
    */
   public int getNumChannels() {
      return channels_.getNumActiveChannels();
   }

   public ChannelSpec getChannels() {
      return channels_;
   }

   public int getNumSlices() {
      return maxSliceIndex_ - minSliceIndex_ + 1;
   }

   public int getMinSliceIndex() {
      return minSliceIndex_;
   }

   public int getMaxSliceIndex() {
      return maxSliceIndex_;
   }

   public boolean isFinished() {
      return finished_;
   }

   public void markAsFinished() {
      finished_ = true;
   }

   public long getStartTime_ms() {
      return startTime_ms_;
   }

   public void setStartTime_ms(long time) {
      startTime_ms_ = time;
   }

   public int getOverlapX() {
      return overlapX_;
   }

   public int getOverlapY() {
      return overlapY_;
   }

   public void waitUntilClosed() {
      imageSaver_.waitForShutdown();
   }

   public String getName() {
      return name_;
   }

   public double getZStep() {
      return zStep_;
   }

   public boolean isPaused() {
      return pause_;
   }

   public void togglePaused() {
      pause_ = !pause_;
      synchronized (pauseLock_) {
         pauseLock_.notifyAll();
      }
   }

   public String[] getChannelNames() {
      return channels_.getActiveChannelNames();
   }

   public Color[] getChannelColors() {
      return channels_.getActiveChannelColors();
   }

}
