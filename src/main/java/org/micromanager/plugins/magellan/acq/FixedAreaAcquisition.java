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

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.awt.geom.Point2D;
import java.util.Iterator;
import java.util.Spliterator;
import java.util.Spliterators;
import java.util.function.Function;
import java.util.stream.Stream;
import java.util.stream.StreamSupport;
import main.java.org.micromanager.plugins.magellan.coordinates.AffineUtils;
import main.java.org.micromanager.plugins.magellan.coordinates.XYStagePosition;
import main.java.org.micromanager.plugins.magellan.json.JSONArray;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.Point3d;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridManager;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceInterpolator;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridListener;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.XYFootprint;

/**
 *
 * @author Henry
 */
public class FixedAreaAcquisition extends Acquisition implements SurfaceGridListener {

   final private FixedAreaAcquisitionSettings settings_;
   private List<XYStagePosition> positions_;
   //executor service to wait for next execution
   private final boolean towardsSampleIsPositive_;
   private long lastTimePointEvent_ = -1;

   /**
    * Acquisition with fixed XY positions (although they can potentially all be
    * translated between time points Supports time points Z stacks that can
    * change at positions between time points
    *
    * Acquisition engine manages a thread that reads events, fixed area
    * acquisition has another thread that generates events
    *
    * @param settings
    * @param acqGroup
    * @throws java.lang.Exception
    */
   public FixedAreaAcquisition(FixedAreaAcquisitionSettings settings) throws Exception {
      super(settings.zStep_, settings.channels_);
      SurfaceGridManager.getInstance().registerSurfaceGridListener(this);
      settings_ = settings;
      try {
         int dir = Magellan.getCore().getFocusDirection(zStage_);
         if (dir > 0) {
            towardsSampleIsPositive_ = true;
         } else if (dir < 0) {
            towardsSampleIsPositive_ = false;
         } else {
            throw new Exception();
         }
      } catch (Exception e) {
         Log.log("Couldn't get focus direction of Z drive. Configre using Tools--Hardware Configuration Wizard");
         throw new RuntimeException();
      }
      createXYPositions();
      initialize(settings.dir_, settings.name_, settings.tileOverlap_);
      createEventGenerator();
   }

   public synchronized void acqSettingsUpdated() {
      //TODO something....
   }

   @Override
   public int getMinSliceIndex() {
      return minSliceIndex_;
   }

   @Override
   public int getMaxSliceIndex() {
      return maxSliceIndex_;
   }

   public double getTimeInterval_ms() {
      return settings_.timePointInterval_ * (settings_.timeIntervalUnit_ == 1 ? 1000 : (settings_.timeIntervalUnit_ == 2 ? 60000 : 1));
   }

   private void createEventGenerator() {
      Log.log("Create event generator started", false);
      eventGenerator_.submit(new Runnable() {
         //check interupt status before any blocking call is entered
         @Override
         public void run() {
            Log.log("event generation beignning", false);
            //get highest possible z position to image, which is slice index 0
            zOrigin_ = getZTopCoordinate();
            boolean tiltedPlane2D = settings_.spaceMode_ == FixedAreaAcquisitionSettings.REGION_2D && settings_.useCollectionPlane_;

            Stream<AcquisitionEvent> eventStream = makeFrameIndexStream().map(timelapse()).flatMap(positions());
            if (tiltedPlane2D) {
               eventStream = eventStream.map(surfaceGuided2D()).flatMap(channels());
            } else if (settings_.channelsAtEverySlice_) {
               eventStream = eventStream.flatMap(zStack()).flatMap(channels());
            } else {
               eventStream = eventStream.flatMap(channels()).flatMap(zStack());
            }

            eventStream.
                    //acqusiition has generated all of its events
                    eventGeneratorShutdown();
         }
      });
   }
   
   
   
   private void submitForAcquisition(AcquisitionEvent event) {
//TODO: need to constanctly check for this???
//         if (eventGenerator_.isShutdown()) {
//            throw new InterruptedException();
//         }
      //keep track of biggest slice index and smallest slice. Maybe needed for display purposes but a little unclear
      maxSliceIndex_ = Math.max(maxSliceIndex_, event.sliceIndex_);
      minSliceIndex_ = Math.min(minSliceIndex_, event.sliceIndex_);
      submitAcquisitionEvent(event);
   }


   private Function<AcquisitionEvent, Stream<AcquisitionEvent>> positions() {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         for (int posIndex = 0; posIndex < positions_.size(); posIndex++) {
            AcquisitionEvent posEvent = event.copy();
            posEvent.positionIndex_ = posIndex;
            posEvent.xyPosition_ = positions_.get(posIndex);
            builder.accept(posEvent);
         }
         return builder.build();
      };
   }

   /**
    * Get a finite stream of integers, stopping whenever what is currently set
    * as the frame in the acquisition settings is reached, thereby allowing it
    * to be changed dynamically during acquisition. Apparently this is much
    * easier in java9 using the takeWhile() function
    *
    * @return
    */
   private Stream<Integer> makeFrameIndexStream() {
      Iterator<Integer> frameIndexIterator = new Iterator() {
         int frameIndex_ = 0;

         @Override
         public boolean hasNext() {
            if (frameIndex_ == 0) {
               return true;
            }
            if (settings_.timeEnabled_ && frameIndex_ < settings_.numTimePoints_) {
               return true;
            }
            return false;
         }

         @Override
         public Object next() {
            frameIndex_++;
            return frameIndex_ - 1;
         }
      };
      Stream<Integer> iStream = StreamSupport.stream(Spliterators.spliteratorUnknownSize(frameIndexIterator, Spliterator.DISTINCT), false);
      return iStream;
   }

   private Function<Integer, AcquisitionEvent> timelapse() {
      return (Integer t) -> {
         double interval_ms = settings_.timePointInterval_ * (settings_.timeIntervalUnit_ == 1 ? 1000 : (settings_.timeIntervalUnit_ == 2 ? 60000 : 1));
         AcquisitionEvent timePointEvent = new AcquisitionEvent(FixedAreaAcquisition.this);
         timePointEvent.miniumumStartTime_ = lastTimePointEvent_ + (long) interval_ms;
         timePointEvent.timeIndex_ = t;
         lastTimePointEvent_ = System.currentTimeMillis();
         return timePointEvent;
      };
   }

   private Function<AcquisitionEvent, Stream<AcquisitionEvent>> channels() {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();
         for (int channelIndex = 0; channelIndex < settings_.channels_.getNumActiveChannels(); channelIndex++) {
            if (!settings_.channels_.getActiveChannelSetting(channelIndex).uniqueEvent_) {
               continue;
            }
            AcquisitionEvent channelEvent = event.copy();
            channelEvent.channelIndex_ = channelIndex;
            channelEvent.zPosition_ += settings_.channels_.getActiveChannelSetting(channelIndex).offset_;
            builder.accept(channelEvent);
         }
         return builder.build();
      };
   }

   private Function<AcquisitionEvent, Stream<AcquisitionEvent>> zStack() {
      return (AcquisitionEvent event) -> {
         Stream.Builder<AcquisitionEvent> builder = Stream.builder();

         int sliceIndex = (int) Math.round((getZTopCoordinate() - zOrigin_) / zStep_);
         while (true) {
//         if (eventGenerator_.isShutdown()) { // check for aborts
//            throw new InterruptedException();
//         }
            double zPos = zOrigin_ + sliceIndex * zStep_;
            if ((settings_.spaceMode_ == FixedAreaAcquisitionSettings.REGION_2D || settings_.spaceMode_ == FixedAreaAcquisitionSettings.NO_SPACE)
                    && sliceIndex > 0) {
               break; //2D regions only have 1 slice
            }

            if (isImagingVolumeUndefinedAtPosition(settings_.spaceMode_, settings_, event.xyPosition_)) {
               break;
            }

            if (isZBelowImagingVolume(settings_.spaceMode_, settings_, event.xyPosition_, zPos, zOrigin_) || (zStageHasLimits_ && zPos > zStageUpperLimit_)) {
               //position is below z stack or limit of focus device, z stack finished
               break;
            }
            //3D region
            if (isZAboveImagingVolume(settings_.spaceMode_, settings_, event.xyPosition_, zPos, zOrigin_) || (zStageHasLimits_ && zPos < zStageLowerLimit_)) {
               sliceIndex++;
               continue; //position is above imaging volume or range of focus device
            }

            AcquisitionEvent sliceEvent = event.copy();
            sliceEvent.sliceIndex_ = sliceIndex;
            //Do plus equals here in case z positions have been modified by another function (e.g. channel specific focal offsets)
            sliceEvent.zPosition_ += zPos;

            builder.accept(sliceEvent);

            //TODO: check if surfaces have been changedp????
            sliceIndex++;
         }//slice loop finish
         return builder.build();
      };

   }

   private Function<AcquisitionEvent, AcquisitionEvent> surfaceGuided2D() {
      return (AcquisitionEvent event) -> {
         //index all slcies as 0, even though they may nto be in the same plane
         double zPos;
         if (settings_.collectionPlane_.getCurentInterpolation().isInterpDefined(
                 event.xyPosition_.getCenter().x, event.xyPosition_.getCenter().y)) {
            zPos = settings_.collectionPlane_.getCurentInterpolation().getInterpolatedValue(
                    event.xyPosition_.getCenter().x, event.xyPosition_.getCenter().y);
         } else {
            zPos = settings_.collectionPlane_.getExtrapolatedValue(event.xyPosition_.getCenter().x, event.xyPosition_.getCenter().y);
         }
         event.zPosition_ += zPos;
         event.sliceIndex_ = 0; //Make these all 0 for the purposes of the display even though they may be in very differnet locations
         return event;
      };

   }

   private void eventGeneratorShutdown() {
      eventGenerator_.shutdown();
      SurfaceGridManager.getInstance().removeSurfaceGridListener(this);
   }

   public static boolean isImagingVolumeUndefinedAtPosition(int spaceMode, FixedAreaAcquisitionSettings settings, XYStagePosition position) {
      if (spaceMode == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
         return !settings.footprint_.isDefinedAtPosition(position);
      } else if (spaceMode == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK) {
         return !settings.topSurface_.isDefinedAtPosition(position)
                 && !settings.bottomSurface_.isDefinedAtPosition(position);
      }
      return false;
   }

   /**
    * This function and the one below determine which slices will be collected
    * for a given position
    *
    * @param position
    * @param zPos
    * @return
    */
   public static boolean isZAboveImagingVolume(int spaceMode, FixedAreaAcquisitionSettings settings, XYStagePosition position, double zPos, double zOrigin) {
      if (spaceMode == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
         boolean extrapolate = settings.fixedSurface_ != settings.footprint_;
         //extrapolate only if different surface used for XY positions than footprint
         return settings.fixedSurface_.isPositionCompletelyAboveSurface(position, settings.fixedSurface_, zPos + settings.distanceAboveFixedSurface_, extrapolate);
      } else if (spaceMode == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK) {
         return settings.topSurface_.isPositionCompletelyAboveSurface(position, settings.topSurface_, zPos + settings.distanceAboveTopSurface_, false);
      } else if (spaceMode == FixedAreaAcquisitionSettings.CUBOID_Z_STACK) {
         return zPos < settings.zStart_;
      } else {
         //no zStack
         return zPos < zOrigin;
      }
   }

   public static boolean isZBelowImagingVolume(int spaceMode, FixedAreaAcquisitionSettings settings, XYStagePosition position, double zPos, double zOrigin) {
      if (spaceMode == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
         boolean extrapolate = settings.fixedSurface_ != settings.footprint_;
         //extrapolate only if different surface used for XY positions than footprint
         return settings.fixedSurface_.isPositionCompletelyBelowSurface(position, settings.fixedSurface_, zPos - settings.distanceBelowFixedSurface_, extrapolate);
      } else if (spaceMode == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK) {
         return settings.bottomSurface_.isPositionCompletelyBelowSurface(position, settings.bottomSurface_, zPos - settings.distanceBelowBottomSurface_, false);
      } else if (spaceMode == FixedAreaAcquisitionSettings.CUBOID_Z_STACK) {
         return zPos > settings.zEnd_;
      } else {
         //no zStack
         return zPos > zOrigin;
      }
   }

   private double getZTopCoordinate() {
      return getZTopCoordinate(settings_.spaceMode_, settings_, towardsSampleIsPositive_, zStageHasLimits_, zStageLowerLimit_, zStageUpperLimit_, zStage_);
   }

   public static double getZTopCoordinate(int spaceMode, FixedAreaAcquisitionSettings settings, boolean towardsSampleIsPositive,
           boolean zStageHasLimits, double zStageLowerLimit, double zStageUpperLimit, String zStage) {
      if (spaceMode == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
         Point3d[] interpPoints = settings.fixedSurface_.getPoints();
         if (towardsSampleIsPositive) {
            double top = interpPoints[0].z - settings.distanceAboveFixedSurface_;
            return zStageHasLimits ? Math.max(zStageLowerLimit, top) : top;
         } else {
            double top = interpPoints[interpPoints.length - 1].z + settings.distanceAboveFixedSurface_;
            return zStageHasLimits ? Math.max(zStageUpperLimit, top) : top;
         }
      } else if (spaceMode == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK) {
         if (towardsSampleIsPositive) {
            Point3d[] interpPoints = settings.topSurface_.getPoints();
            double top = interpPoints[0].z - settings.distanceAboveTopSurface_;
            return zStageHasLimits ? Math.max(zStageLowerLimit, top) : top;
         } else {
            Point3d[] interpPoints = settings.topSurface_.getPoints();
            double top = interpPoints[interpPoints.length - 1].z + settings.distanceAboveTopSurface_;
            return zStageHasLimits ? Math.max(zStageLowerLimit, top) : top;
         }
      } else if (spaceMode == FixedAreaAcquisitionSettings.CUBOID_Z_STACK) {
         return settings.zStart_;
      } else {
         try {
            //region2D or no region
            return Magellan.getCore().getPosition(zStage);
         } catch (Exception ex) {
            Log.log("couldn't get z position", true);
            throw new RuntimeException();
         }
      }
   }

   //TODO: this could be generalized into a method to get metadata specific to any acwuisiton surface type
   public JSONArray getFixedSurfacePoints() {
      Point3d[] points = settings_.fixedSurface_.getPoints();
      JSONArray pointArray = new JSONArray();
      for (Point3d p : points) {
         pointArray.put(p.x + "_" + p.y + "_" + p.z);
      }
      return pointArray;
   }

   public int getSpaceMode() {
      return settings_.spaceMode_;
   }

   private void createXYPositions() {
      try {
         //get XY positions
         if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK) {
            positions_ = settings_.footprint_.getXYPositions(settings_.tileOverlap_);
         } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK) {
            positions_ = settings_.useTopOrBottomFootprint_ == FixedAreaAcquisitionSettings.FOOTPRINT_FROM_TOP
                    ? settings_.topSurface_.getXYPositions(settings_.tileOverlap_) : settings_.bottomSurface_.getXYPositions(settings_.tileOverlap_);
         } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.CUBOID_Z_STACK) {
            positions_ = settings_.footprint_.getXYPositions(settings_.tileOverlap_);
         } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.REGION_2D) {
            positions_ = settings_.footprint_.getXYPositions(settings_.tileOverlap_);
         } else {
            //no space mode, use current stage positon
            positions_ = new ArrayList<XYStagePosition>();
            int fullTileWidth = (int) Magellan.getCore().getImageWidth();
            int fullTileHeight = (int) Magellan.getCore().getImageHeight();
            int tileWidthMinusOverlap = fullTileWidth - this.getOverlapX();
            int tileHeightMinusOverlap = fullTileHeight - this.getOverlapY();
            Point2D.Double currentStagePos = Magellan.getCore().getXYStagePosition(xyStage_);
            positions_.add(new XYStagePosition(currentStagePos, tileWidthMinusOverlap, tileHeightMinusOverlap, fullTileWidth, fullTileHeight, 0, 0,
                    AffineUtils.getAffineTransform(Magellan.getCore().getCurrentPixelSizeConfig(),
                            currentStagePos.x, currentStagePos.y)));
         }
      } catch (Exception e) {
         Log.log("Problem with Acquisition's XY positions. Check acquisition settings");
         throw new RuntimeException();
      }
   }

   @Override
   protected JSONArray createInitialPositionList() {
      JSONArray pList = new JSONArray();
      for (XYStagePosition xyPos : positions_) {
         pList.put(xyPos.getMMPosition());
      }
      return pList;
   }

   @Override
   public void SurfaceOrGridChanged(XYFootprint f) {
      boolean updateNeeded = false;
      if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK && settings_.fixedSurface_ == f) {
         updateNeeded = true;
      } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK
              && (settings_.topSurface_ == f || settings_.bottomSurface_ == f)) {
         updateNeeded = true;
      } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.CUBOID_Z_STACK) {

      } else if (settings_.spaceMode_ == FixedAreaAcquisitionSettings.REGION_2D) {

      } else {
         //no space mode
      }

      if (updateNeeded) {
         acqSettingsUpdated();
      }
   }

   @Override
   public void SurfaceOrGridDeleted(XYFootprint f) {
      //
   }

   @Override
   public void SurfaceOrGridCreated(XYFootprint f) {
      //
   }

   @Override
   public void SurfaceOrGridRenamed(XYFootprint f) {
      //
   }

   @Override
   public void SurfaceInterpolationUpdated(SurfaceInterpolator s) {
      //
   }

}
