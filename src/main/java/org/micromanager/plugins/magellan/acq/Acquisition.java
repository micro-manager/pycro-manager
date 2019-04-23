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
import java.awt.geom.AffineTransform;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import static main.java.org.micromanager.plugins.magellan.acq.MagellanGUIAcquisition.isImagingVolumeUndefinedAtPosition;
import static main.java.org.micromanager.plugins.magellan.acq.MagellanGUIAcquisition.isZAboveImagingVolume;
import static main.java.org.micromanager.plugins.magellan.acq.MagellanGUIAcquisition.isZBelowImagingVolume;
import main.java.org.micromanager.plugins.magellan.channels.ChannelSpec;
import main.java.org.micromanager.plugins.magellan.coordinates.AffineUtils;
import main.java.org.micromanager.plugins.magellan.coordinates.PositionManager;
import main.java.org.micromanager.plugins.magellan.coordinates.XYStagePosition;
import main.java.org.micromanager.plugins.magellan.json.JSONArray;
import main.java.org.micromanager.plugins.magellan.json.JSONObject;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.misc.MD;
import mmcorej.CMMCore;

/**
 * Abstract class that manages a generic acquisition. Subclassed into specific
 * types of acquisition
 */
public abstract class Acquisition {

   private static final int MAX_QUEUED_IMAGES_FOR_WRITE = 50;

   protected final double zStep_;
   protected double zOrigin_;
   protected volatile int minSliceIndex_ = 0, maxSliceIndex_ = 0;
   protected String xyStage_, zStage_;
   protected boolean zStageHasLimits_ = false;
   protected double zStageLowerLimit_, zStageUpperLimit_;
   protected AcquisitionEvent lastEvent_ = null;
   protected volatile boolean finished_ = false;
   private String name_;
   private long startTime_ms_ = -1;
   private int overlapX_, overlapY_;
   private volatile boolean pause_ = false;
   private Object pauseLock_ = new Object();
   protected ChannelSpec channels_;
   private MMImageCache imageCache_;
   private ThreadPoolExecutor savingExecutor_;
   private ExecutorService eventGenerator_;
   protected PositionManager posManager_;
   private MagellanEngine eng_;

   public Acquisition(double zStep, ChannelSpec channels) {
      eng_ = MagellanEngine.getInstance();
      xyStage_ = Magellan.getCore().getXYStageDevice();
      zStage_ = Magellan.getCore().getFocusDevice();
      channels_ = channels;
      //"postion" is not generic name..and as of right now there is now way of getting generic z positions
      //from a z deviec in MM
      String positionName = "Position";
      try {
         if (Magellan.getCore().hasProperty(zStage_, positionName)) {
            zStageHasLimits_ = Magellan.getCore().hasPropertyLimits(zStage_, positionName);
            if (zStageHasLimits_) {
               zStageLowerLimit_ = Magellan.getCore().getPropertyLowerLimit(zStage_, positionName);
               zStageUpperLimit_ = Magellan.getCore().getPropertyUpperLimit(zStage_, positionName);
            }
         }
      } catch (Exception ex) {
         Log.log("Problem communicating with core to get Z stage limits");
      }
      zStep_ = zStep;
   }

   protected void initialize(String dir, String name, double overlapPercent) {
      overlapX_ = (int) (Magellan.getCore().getImageWidth() * overlapPercent / 100);
      overlapY_ = (int) (Magellan.getCore().getImageHeight() * overlapPercent / 100);
      JSONObject summaryMetadata = makeSummaryMD(name);
      MultiResMultipageTiffStorage imageStorage = new MultiResMultipageTiffStorage(dir, summaryMetadata);
      posManager_ = imageStorage.getPosManager();
      //storage class has determined unique acq name, so it can now be stored
      name_ = imageStorage.getUniqueAcqName();
      imageCache_ = new MMImageCache(imageStorage);
      imageCache_.setSummaryMetadata(summaryMetadata);
      new DisplayPlus(imageCache_, this, summaryMetadata, imageStorage);
      savingExecutor_ = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new LinkedBlockingQueue<Runnable>(),
              (Runnable r) -> new Thread(r, name_ + ": Saving xecutor"));
      eventGenerator_ = Executors.newSingleThreadExecutor((Runnable r) -> new Thread(r, name_ + ": Event generator"));
      //subclasses are resonsible for submitting event streams to begin acquisiton
   }

   /**
    * Called by acquisition subclasses to communicate with acquisition engine
    * returns a Future that can be gotten once the last image has written to
    * disk
    *
    * @param eventStream
    * @return
    */
   protected void submitEventStream(Stream<AcquisitionEvent> eventStream) {
      eventGenerator_.submit(() -> {
         //Submit stream to acqusition event for execution, getting a stream of Future<Future>
         //This won't actually do anything until the terminal operation on the stream has taken place

         Stream<Future<Future>> eventFutureStream = eng_.mapToAcquisition(eventStream);
        
         //Make sure events can't be submitted to the engine way faster than images can be written to disk
         eventFutureStream = eventFutureStream.map(new Function<Future<Future>, Future<Future>>() {
            @Override
            public Future<Future> apply(Future<Future> t) {
               while (savingExecutor_.getQueue().size() > MAX_QUEUED_IMAGES_FOR_WRITE) {
                  try {
                     Thread.sleep(2);
                  } catch (InterruptedException ex) {
                     throw new RuntimeException(ex); //must have beeen aborted
                  }
               }
               return t;
            }

            //TODO: add something that checks for canellatio on abort?
         });

         try {
            //make sure last one has written to disk
            Future<Future> lastEventSubmittedFuture = eventFutureStream.reduce((first, second) -> second).get();
            Future lastImageSavedFuture = lastEventSubmittedFuture.get();
            lastImageSavedFuture.get();
         } catch (InterruptedException ex) {
            //Acquition aborted
         } catch (ExecutionException ex) {
            //Problem with acquisition or with saving TODO something
            ex.printStackTrace();
            throw new RuntimeException(ex);
         }

      });
   }

   /**
    * Function for lazy conversion a stream of acquisition events to another
    * stream by applying a event2stream function to each element of the
    * inputStream
    *
    * @return
    */
   protected Function<Stream<AcquisitionEvent>, Stream<AcquisitionEvent>> stream2Stream(
           Function<AcquisitionEvent, Stream<AcquisitionEvent>> event2StreamFunction) {
      return (Stream<AcquisitionEvent> inputStream) -> {
         //make a stream builder
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         //apply the function to each element of the input stream, then send the resulting streams
         //to the builder
         inputStream.spliterator().forEachRemaining((AcquisitionEvent t) -> {
            Stream<AcquisitionEvent> subStream = event2StreamFunction.apply(t);
            subStream.spliterator().forEachRemaining(builder);
         });
         return builder.build();
      };
   }

   /**
    * Called by acquisition engine to save an image, returns a future that can
    * be gotten once that image has made it onto the disk
    */
   Future saveImage(MagellanTaggedImage image) {
      //The saving executor is essentially doing the work of making the image pyramid, while there
      //is a seperate internal executor in MultiResMultipageTiffStorage that does all the writing
      return savingExecutor_.submit(() -> {
         if (MagellanTaggedImage.isAcquisitionFinishedImage(image)) {
            imageCache_.finished();
            finished_ = true;
         } else {
            //this method doesnt return until all images have been writtent to disk
            imageCache_.putImage(image);
         }
      });
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
//            if (Acquisition.this.isPaused()) {
//               Acquisition.this.togglePaused();
//            }
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

            //signal acquisition engine to start finishing process
            Future<Future> endAcqFuture = eng_.mapToAcquisition(Stream.of(AcquisitionEvent.createAcquisitionFinishedEvent(Acquisition.this))).findFirst().get();
            Future imageSaverDoneFuture;
            try {
               imageSaverDoneFuture = endAcqFuture.get();
               imageSaverDoneFuture.get();
            } catch (InterruptedException ex) {
               Log.log("aborting acquisition interrupted");
            } catch (ExecutionException ex) {
               Log.log("Exception encountered when trying to end acquisition", true);
            }
             savingExecutor_.shutdown();
            try {
               while (!savingExecutor_.awaitTermination(5, TimeUnit.MILLISECONDS)) {
               }
            } catch (InterruptedException ex) {
               Log.log("Unexpected interrupt while trying to abort acquisition", true);
               //shouldn't happen
            }
         }
      }, "Aborting thread").start();
   }

   private JSONObject makeSummaryMD(String prefix) {
      //num channels is camera channels * acquisitionChannels
      int numChannels = this.getNumChannels();

      CMMCore core = Magellan.getCore();
      JSONObject summary = new JSONObject();
      MD.setAcqDate(summary, getCurrentDateAndTime());
      //Actual number of channels is equal or less than this field
      MD.setNumChannels(summary, numChannels);

      MD.setZCTOrder(summary, false);
      MD.setPixelTypeFromByteDepth(summary, (int) Magellan.getCore().getBytesPerPixel());
      MD.setBitDepth(summary, (int) Magellan.getCore().getImageBitDepth());
      MD.setWidth(summary, (int) Magellan.getCore().getImageWidth());
      MD.setHeight(summary, (int) Magellan.getCore().getImageHeight());
      MD.setSavingPrefix(summary, prefix);
      JSONArray initialPosList = this.createInitialPositionList();
      MD.setInitialPositionList(summary, initialPosList);
      MD.setPixelSizeUm(summary, core.getPixelSizeUm());
      MD.setZStepUm(summary, this.getZStep());
      MD.setIntervalMs(summary, this instanceof MagellanGUIAcquisition ? ((MagellanGUIAcquisition) this).getTimeInterval_ms() : 0);
      MD.setPixelOverlapX(summary, this.getOverlapX());
      MD.setPixelOverlapY(summary, this.getOverlapY());
      MD.setExploreAcq(summary, this instanceof ExploreAcquisition);
      //affine transform
      String pixelSizeConfig;
      try {
         pixelSizeConfig = core.getCurrentPixelSizeConfig();
      } catch (Exception ex) {
         Log.log("couldn't get affine transform");
         throw new RuntimeException();
      }
      AffineTransform at = AffineUtils.getAffineTransform(pixelSizeConfig, 0, 0);
      if (at == null) {
         Log.log("No affine transform found for pixel size config: " + pixelSizeConfig
                 + "\nUse \"Calibrate\" button on main Magellan window to configure\n\n");
         throw new RuntimeException();
      }
      MD.setAffineTransformString(summary, AffineUtils.transformToString(at));
      JSONArray chNames = new JSONArray();
      JSONArray chColors = new JSONArray();
      String[] names = this.getChannelNames();
      Color[] colors = this.getChannelColors();
      for (int i = 0; i < numChannels; i++) {
         chNames.put(names[i]);
         chColors.put(colors[i].getRGB());
      }
      MD.setChannelNames(summary, chNames);
      MD.setChannelColors(summary, chColors);
      try {
         MD.setCoreXY(summary, Magellan.getCore().getXYStageDevice());
         MD.setCoreFocus(summary, Magellan.getCore().getFocusDevice());
      } catch (Exception e) {
         Log.log("couldn't get XY or Z stage from core");
      }
      return summary;
   }

   public static void main(String[] args) {
      Stream<AcquisitionEvent> eventStream = Stream.of(new AcquisitionEvent(null));
      eventStream = eventStream.map(new Function<AcquisitionEvent, AcquisitionEvent>() {
         @Override
         public AcquisitionEvent apply(AcquisitionEvent t) {
            System.out.println("Stream consuming now");
            return t;
         }
      });
      eventStream.collect(Collectors.toList());
   }

   /**
    * Build a lazy stream of events based on the hierarchy of acquisition
    * functions
    *
    * @param acqFunctions
    * @return
    */
   protected Stream<AcquisitionEvent> makeEventStream(List<Function<AcquisitionEvent, Stream<AcquisitionEvent>>> acqFunctions) {
      //Make a composed function that expands every level of the acquisition tree as needed
      Function<AcquisitionEvent, Stream<AcquisitionEvent>> composedFunction = acqFunctions.get(0);
      for (int i = 1; i < acqFunctions.size(); i++) {
         composedFunction = composedFunction.andThen(stream2Stream(acqFunctions.get(i)));
      }
      //Start with a root event and lazily map all functions to it as needed
      Stream<AcquisitionEvent> eventStream = Stream.of(new AcquisitionEvent(this));
      Stream<Stream<AcquisitionEvent>> streamOStreams = eventStream.map(composedFunction);
      eventStream = streamOStreams.reduce((stream1, stream2) -> {
         return Stream.concat(stream1, stream2);
      }).get();
      //keep track of min and max slice indices as events are submitted
      return eventStream;
   }

   protected Function<AcquisitionEvent, Stream<AcquisitionEvent>> channels(ChannelSpec channels) {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         for (int channelIndex = 0; channelIndex < channels.getNumActiveChannels(); channelIndex++) {
            if (!channels.getActiveChannelSetting(channelIndex).uniqueEvent_) {
               continue;
            }
            AcquisitionEvent channelEvent = event.copy();
            channelEvent.channelIndex_ = channelIndex;
            channelEvent.zPosition_ += channels.getActiveChannelSetting(channelIndex).offset_;
            builder.accept(channelEvent);
         }
         return builder.build();
      };
   }

   protected Function<AcquisitionEvent, Stream<AcquisitionEvent>> zStack(int startSliceIndex, int stopSliceIndex) {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         for (int sliceIndex = startSliceIndex; sliceIndex < stopSliceIndex; sliceIndex++) {
            double zPos = sliceIndex * zStep_ + zOrigin_;
            AcquisitionEvent sliceEvent = event.copy();
            sliceEvent.sliceIndex_ = sliceIndex;
            //Do plus equals here in case z positions have been modified by another function (e.g. channel specific focal offsets)
            sliceEvent.zPosition_ += zPos;
            builder.accept(sliceEvent);
         }//slice loop finish
         return builder.build();
      };
   }

//   protected Function<AcquisitionEvent, Stream<AcquisitionEvent>> zStack(double start, double stop) {
//      return (AcquisitionEvent event) -> {
//         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
//         for (double zPos=start; zPos < stop; zPos += zStep_) {
//            int sliceIndex = (int) Math.round((start - zOrigin_) / zStep_);
//            AcquisitionEvent sliceEvent = event.copy();
//            sliceEvent.sliceIndex_ = sliceIndex;
//            //Do plus equals here in case z positions have been modified by another function (e.g. channel specific focal offsets)
//            sliceEvent.zPosition_ += zPos;
//            builder.accept(sliceEvent);
//            sliceIndex++;
//         }//slice loop finish
//         return builder.build();
//      };
//   }
   protected Function<AcquisitionEvent, Stream<AcquisitionEvent>> positions(
           int[] positionIndices, List<XYStagePosition> positions) {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         for (int index = 0; index < positionIndices.length; index++) {
            AcquisitionEvent posEvent = event.copy();
            posEvent.positionIndex_ = positionIndices[index];
            posEvent.xyPosition_ = positions.get(posEvent.positionIndex_);
            builder.accept(posEvent);
         }
         return builder.build();
      };
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
      try {
         //wait for it to exit
         while (!eventGenerator_.awaitTermination(5, TimeUnit.MILLISECONDS)) {
         }
         while (!savingExecutor_.awaitTermination(5, TimeUnit.MILLISECONDS)) {
         }
      } catch (InterruptedException ex) {
         Log.log("Unexpected interrupt while trying to abort acquisition", true);
         //shouldn't happen
      }
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

   private static String getCurrentDateAndTime() {
      DateFormat df = new SimpleDateFormat("yyyy/MM/dd HH:mm:ss");
      Calendar calobj = Calendar.getInstance();
      return df.format(calobj.getTime());
   }

}
