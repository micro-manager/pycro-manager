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

/*
 * To change this template, choose Tools | Templates and open the template in
 * the editor.
 */
import java.awt.Color;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.awt.geom.AffineTransform;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import main.java.org.micromanager.plugins.magellan.channels.ChannelSetting;
import main.java.org.micromanager.plugins.magellan.coordinates.AffineUtils;
import main.java.org.micromanager.plugins.magellan.json.JSONArray;
import main.java.org.micromanager.plugins.magellan.json.JSONException;
import main.java.org.micromanager.plugins.magellan.json.JSONObject;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.GlobalSettings;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.misc.MD;
import mmcorej.CMMCore;
import mmcorej.TaggedImage;

/**
 * Engine has a single thread executor, which sits idly waiting for new
 * acquisitions when not in use
 */
public class MagellanEngine {

   private static final int DEMO_DELAY_Z = 0;
   private static final int DEMO_DELAY_XY = 0;
   private static final int DEMO_DELAY_IMAGE_CAPTURE = 0;

   private static final int MAX_ACQUIRED_IMAGES_WAITING_TO_SAVE = 40;

   
   private static final int HARDWARE_ERROR_RETRIES = 6;
   private static final int DELAY_BETWEEN_RETRIES_MS = 5;
   private static CMMCore core_;
   private static MagellanEngine singleton_;
   private AcquisitionEvent lastEvent_ = null;
   private ExploreAcquisition currentExploreAcq_;
   private FixedAreaAcquisition currentFixedAcqs_;
   private AcquisitionsManager multiAcqManager_;
   private final ExecutorService acqExecutor_;
   private AcqDurationEstimator acqDurationEstiamtor_; //get information about how much time different hardware moves take

   public MagellanEngine(CMMCore core, AcqDurationEstimator acqDurationEstiamtor) {
      singleton_ = this;
      core_ = core;
      acqDurationEstiamtor_ = acqDurationEstiamtor;
      acqExecutor_ = Executors.newSingleThreadExecutor(r -> {
         return new Thread(r, "Magellan Acquisition Engine Thread");
      });
   }

   public static MagellanEngine getInstance() {
      return singleton_;
   }
   
   
   
   /**
    * Just submit it for later execution. Won't block, will return a Future
    * @param e 
    */
   public Future<Future> submitEvent(AcquisitionEvent e) {
      return acqExecutor_.submit(new Callable() {
         @Override
         public Future call() throws Exception {
            return executeAcquisitionEvent(e);
         }
      });
   }

   
   
   /**
    * Submit a stream of acquisition events for acquisition. 
    * 
    *
    * Returns a Future<Future>. The first get returns when the last event has 
    * been acquired, the second returns when the when its image has been written to disk
    * 
    *  @return
    */
   public void acquire(Stream<AcquisitionEvent> eventStream) {
      
      //TODO: some processing to make things optimized when sequenceable hardware is present
     
      Stream<Future<Future>> futureStream = eventStream.map((AcquisitionEvent event) -> {
         Future<Future> imageAcquiredFuture = acqExecutor_.submit(new Callable() {
            @Override
            public Object call() throws Exception {
               Future future = executeAcquisitionEvent(event);
               return future;
            }
         });
         return imageAcquiredFuture;
      });
      
      //TODO: or perhaps you want to return and do this in the acquisition code,
      // because that way it can handle its own exceptions and maybe even cancel
      //subsequent events
      //Map through all of these futures, checking for Exceptions
      //Then if nothing wrong map the the futures of the futures
      //Finally return when the last image has been written to disk
      futureStream.map(new Function<Future<Future>, R>)
      
              
      List<AcquisitionEvent> eventList = eventStream.collect(Collectors.toList());
      
   }

   /**
    * Returns a future that returns when the image has been successfully written
    * to disk
    *
    * @param event
    * @return
    * @throws InterruptedException
    */
   private Future executeAcquisitionEvent(final AcquisitionEvent event) throws InterruptedException {
      if (event.isAcquisitionFinishedEvent()) {
         //signal to MagellanTaggedImageSink to finish saving thread and mark acquisition as finished
         return event.acquisition_.saveImage(new SignalTaggedImage(SignalTaggedImage.AcqSingal.AcqusitionFinsihed));
      } else {
         updateHardware(event);
         return acquireImage(event);
      }
   }

   private Future acquireImage(final AcquisitionEvent event) throws InterruptedException, HardwareControlException {
      double startTime = System.currentTimeMillis();
      loopHardwareCommandRetries(new Runnable() {
         @Override
         public void run() {
            try {
               Magellan.getCore().snapImage();
            } catch (Exception ex) {
               throw new HardwareControlException(ex.getMessage());
            }
         }
      }, "snapping image");

      //get elapsed time
      final long currentTime = System.currentTimeMillis();
      if (event.acquisition_.getStartTime_ms() == -1) {
         //first image, initialize
         event.acquisition_.setStartTime_ms(currentTime);
      }

      ArrayList<MagellanTaggedImage> images = new ArrayList<MagellanTaggedImage>();
      for (int c = 0; c < core_.getNumberOfCameraChannels(); c++) {
         TaggedImage ti = null;
         try {
            ti = core_.getTaggedImage(c);
         } catch (Exception ex) {
            throw new HardwareControlException(ex.getMessage());
         }
         MagellanTaggedImage img = convertTaggedImage(ti);
         MagellanEngine.addImageMetadata(img.tags, event, event.timeIndex_, c, currentTime - event.acquisition_.getStartTime_ms(),
                 event.acquisition_.channels_.getActiveChannelSetting(event.channelIndex_).exposure_);
         images.add(img);
      }

      //send to storage
      Future imageSavedFuture = null;
      for (int c = 0; c < images.size(); c++) {
         imageSavedFuture = event.acquisition_.saveImage(images.get(c));
      }
      //keep track of how long it takes to acquire an image for acquisition duration estimation
      try {
         acqDurationEstiamtor_.storeImageAcquisitionTime(
                 event.acquisition_.channels_.getActiveChannelSetting(event.channelIndex_).exposure_, System.currentTimeMillis() - startTime);
      } catch (Exception ex) {
         Log.log(ex);
      }
      //Return the last image, which should not allow result to be gotten until all previous ones have been saved
      return imageSavedFuture;
   }

   private void updateHardware(final AcquisitionEvent event) throws InterruptedException, HardwareControlException {
      //compare to last event to see what needs to change
      if (lastEvent_ != null && lastEvent_.acquisition_ != event.acquisition_) {
         lastEvent_ = null; //update all hardware if switching to a new acquisition
      }
      //Get the hardware specific to this acquisition
      final String xyStage = event.acquisition_.getXYStageName();
      final String zStage = event.acquisition_.getZStageName();

      //move Z before XY 
      /////////////////////////////Z stage/////////////////////////////
      if (lastEvent_ == null || event.zPosition_ != lastEvent_.zPosition_ || event.positionIndex_ != lastEvent_.positionIndex_) {
         double startTime = System.currentTimeMillis();
         //wait for it to not be busy (is this even needed?)
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  while (core_.deviceBusy(zStage)) {
                     Thread.sleep(1);
                  }
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "waiting for Z stage to not be busy");
         //move Z stage
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  core_.setPosition(zStage, event.zPosition_);
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "move Z device");
         //wait for it to not be busy (is this even needed?)
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  while (core_.deviceBusy(zStage)) {
                     Thread.sleep(1);
                  }
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "waiting for Z stage to not be busy");
         try {
            acqDurationEstiamtor_.storeZMoveTime(System.currentTimeMillis() - startTime);
         } catch (Exception ex) {
            Log.log(ex);
         }
      }

      /////////////////////////////XY Stage/////////////////////////////
      if (lastEvent_ == null || event.positionIndex_ != lastEvent_.positionIndex_) {
         double startTime = System.currentTimeMillis();
         //wait for it to not be busy (is this even needed??)
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  while (core_.deviceBusy(xyStage)) {
                     Thread.sleep(1);
                  }
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "waiting for XY stage to not be busy");
         //move to new position
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  core_.setXYPosition(xyStage, event.xyPosition_.getCenter().x, event.xyPosition_.getCenter().y);
                  //delay in demo mode to simulate movement
                  if (GlobalSettings.getInstance().getDemoMode()) {
                     Thread.sleep(DEMO_DELAY_XY);
                  }
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "moving XY stage");
         //wait for it to not be busy (is this even needed??)
         loopHardwareCommandRetries(new Runnable() {
            @Override
            public void run() {
               try {
                  while (core_.deviceBusy(xyStage)) {
                     Thread.sleep(1);
                  }
               } catch (Exception ex) {
                  throw new HardwareControlException(ex.getMessage());
               }
            }
         }, "waiting for XY stage to not be busy");
         try {
            acqDurationEstiamtor_.storeXYMoveTime(System.currentTimeMillis() - startTime);
         } catch (Exception ex) {
            Log.log(ex);
         }
      }

      /////////////////////////////Channels/////////////////////////////
      if (lastEvent_ == null || event.channelIndex_ != lastEvent_.channelIndex_
              && event.acquisition_.channels_ != null && event.acquisition_.channels_.getNumActiveChannels() != 0) {
         double startTime = System.currentTimeMillis();
         try {
            final ChannelSetting setting = event.acquisition_.channels_.getActiveChannelSetting(event.channelIndex_);
            if (setting.use_ && setting.config_ != null) {
               loopHardwareCommandRetries(new Runnable() {
                  @Override
                  public void run() {
                     try {
                        //set exposure
                        core_.setExposure(setting.exposure_);
                        //set other channel props
                        core_.setConfig(setting.group_, setting.config_);
                        core_.waitForConfig(setting.group_, setting.config_);
                     } catch (Exception ex) {
                        throw new HardwareControlException(ex.getMessage());
                     }
                  }
               }, "Set channel group");
            }

         } catch (Exception ex) {
            Log.log("Couldn't change channel group");
         }
         try {
            acqDurationEstiamtor_.storeChannelSwitchTime(System.currentTimeMillis() - startTime);
         } catch (Exception ex) {
            Log.log(ex);
         }
      }
      lastEvent_ = event;
   }

   private void loopHardwareCommandRetries(Runnable r, String commandName) throws InterruptedException, HardwareControlException {
      for (int i = 0; i < HARDWARE_ERROR_RETRIES; i++) {
         try {
            r.run();
         } catch (Exception e) {
            e.printStackTrace();
            Log.log(getCurrentDateAndTime() + ": Problem " + commandName + "\n Retry #" + i + " in " + DELAY_BETWEEN_RETRIES_MS + " ms", true);
            Thread.sleep(DELAY_BETWEEN_RETRIES_MS);
         }
      }
      Log.log(commandName + " unsuccessful", true);
      throw new HardwareControlException();
   }

   private static String getCurrentDateAndTime() {
      DateFormat df = new SimpleDateFormat("yyyy/MM/dd HH:mm:ss");
      Calendar calobj = Calendar.getInstance();
      return df.format(calobj.getTime());
   }

   private static void addImageMetadata(JSONObject tags, AcquisitionEvent event, int timeIndex,
           int camChannelIndex, long elapsed_ms, double exposure) {
      //add tags
      try {
         long gridRow = event.gridRow_;
         long gridCol = event.gridCol_;
         MD.setPositionName(tags, "Grid_" + event.gridRow_ + "_" + event.gridCol_);
         MD.setPositionIndex(tags, event.positionIndex_);
         MD.setSliceIndex(tags, event.sliceIndex_);
         MD.setFrameIndex(tags, timeIndex);
         MD.setChannelIndex(tags, event.channelIndex_ + camChannelIndex);
         MD.setZPositionUm(tags, event.zPosition_);
         MD.setElapsedTimeMs(tags, elapsed_ms);
         MD.setImageTime(tags, (new SimpleDateFormat("yyyy-MM-dd HH:mm:ss -")).format(Calendar.getInstance().getTime()));
         MD.setExposure(tags, exposure);
         MD.setGridRow(tags, gridRow);
         MD.setGridCol(tags, gridCol);
         MD.setStageX(tags, event.xyPosition_.getCenter().x);
         MD.setStageY(tags, event.xyPosition_.getCenter().y);
         //add data about surface
         //right now this only works for fixed distance from the surface
         if ((event.acquisition_ instanceof FixedAreaAcquisition)
                 && ((FixedAreaAcquisition) event.acquisition_).getSpaceMode() == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
            //add metadata about surface
            MD.setSurfacePoints(tags, ((FixedAreaAcquisition) event.acquisition_).getFixedSurfacePoints());
         }
      } catch (Exception e) {
         Log.log("Problem adding image metadata");
         throw new RuntimeException();
      }
   }

   public static JSONObject makeSummaryMD(Acquisition acq, String prefix) {
      //num channels is camera channels * acquisitionChannels
      int numChannels = acq.getNumChannels();

      CMMCore core = Magellan.getCore();
      JSONObject summary = new JSONObject();
      MD.setAcqDate(summary, getCurrentDateAndTime());
      //Actual number of channels is equal or less than this field
      MD.setNumChannels(summary, numChannels);

      MD.setZCTOrder(summary, false);
      MD.setPixelTypeFromByteDepth(summary, (int) core_.getBytesPerPixel());
      MD.setBitDepth(summary, (int) core_.getImageBitDepth());
      MD.setWidth(summary, (int) Magellan.getCore().getImageWidth());
      MD.setHeight(summary, (int) Magellan.getCore().getImageHeight());
      MD.setSavingPrefix(summary, prefix);
      JSONArray initialPosList = acq.createInitialPositionList();
      MD.setInitialPositionList(summary, initialPosList);
      MD.setPixelSizeUm(summary, core.getPixelSizeUm());
      MD.setZStepUm(summary, acq.getZStep());
      MD.setIntervalMs(summary, acq instanceof FixedAreaAcquisition ? ((FixedAreaAcquisition) acq).getTimeInterval_ms() : 0);
      MD.setPixelOverlapX(summary, acq.getOverlapX());
      MD.setPixelOverlapY(summary, acq.getOverlapY());
      MD.setExploreAcq(summary, acq instanceof ExploreAcquisition);
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
      String[] names = acq.getChannelNames();
      Color[] colors = acq.getChannelColors();
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

   private static MagellanTaggedImage convertTaggedImage(TaggedImage img) {
      try {
         return new MagellanTaggedImage(img.pix, new JSONObject(img.tags.toString()));
      } catch (JSONException ex) {
         Log.log("Couldn't convert JSON metadata");
         throw new RuntimeException();
      }
   }

   public void setMultiAcqManager(AcquisitionsManager multiAcqManager) {
      multiAcqManager_ = multiAcqManager;
   }
}

class HardwareControlException extends RuntimeException {

   public HardwareControlException() {
      super();
   }

   public HardwareControlException(String s) {
      super(s);
   }
}
