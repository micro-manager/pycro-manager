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

import java.awt.Color;
import java.util.ArrayList;
import java.util.prefs.Preferences;
import main.java.org.micromanager.plugins.magellan.channels.ChannelSetting;
import main.java.org.micromanager.plugins.magellan.channels.ChannelSpec;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceInterpolator;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.XYFootprint;

/**
 *
 * @author Henry
 */
public class AcquisitionSettings  {
   
   public static final String PREF_PREFIX = "Fixed area acquisition ";

   public static final int NO_SPACE = 0;
   public static final int CUBOID_Z_STACK = 1;
   public static final int SURFACE_FIXED_DISTANCE_Z_STACK = 2;
   public static final int VOLUME_BETWEEN_SURFACES_Z_STACK = 3;
   public static final int REGION_2D = 4;
   public static final int TIME_MS = 0;
   public static final int TIME_S = 1;
   public static final int TIME_MIN = 2;
   public static int FOOTPRINT_FROM_TOP = 0, FOOTPRINT_FROM_BOTTOM = 1;
   
   //saving
   public String dir_, name_;
   //time
   public boolean timeEnabled_;
   public double timePointInterval_;
   public int numTimePoints_;
   public int timeIntervalUnit_; 

   //space
   public double zStep_, zStart_, zEnd_, distanceBelowFixedSurface_, distanceAboveFixedSurface_,
           distanceAboveTopSurface_, distanceBelowBottomSurface_;
   public int spaceMode_;
   public boolean useCollectionPlane_ = false;
   public SurfaceInterpolator topSurface_, bottomSurface_, fixedSurface_, collectionPlane_;
   public XYFootprint footprint_;
   public int useTopOrBottomFootprint_;
   public double tileOverlap_; //stored as percent * 100, i.e. 55 => 55%
   public boolean channelsAtEverySlice_;
   
   //channels
   public String channelGroup_;
   public ChannelSpec channels_ ;

   public AcquisitionSettings() {
      Preferences prefs = Magellan.getPrefs();
      name_ = prefs.get(PREF_PREFIX + "NAME", "Untitled");
      timeEnabled_ = prefs.getBoolean(PREF_PREFIX + "TE", false);
      timePointInterval_ = prefs.getDouble(PREF_PREFIX + "TPI", 0);
      numTimePoints_ = prefs.getInt(PREF_PREFIX + "NTP", 1);
      timeIntervalUnit_ = prefs.getInt(PREF_PREFIX + "TPIU", 0);
      //space
      useCollectionPlane_ = prefs.getBoolean(PREF_PREFIX +"USECOLLECTIONPLANE", false);
      channelsAtEverySlice_ = prefs.getBoolean(PREF_PREFIX +"ACQORDER", true);
      zStep_ = prefs.getDouble(PREF_PREFIX + "ZSTEP", 1);
      zStart_ = prefs.getDouble(PREF_PREFIX + "ZSTART", 0);
      zEnd_ = prefs.getDouble(PREF_PREFIX + "ZEND", 0);
      distanceBelowFixedSurface_ = prefs.getDouble(PREF_PREFIX + "ZDISTBELOWFIXED", 0);
      distanceAboveFixedSurface_ = prefs.getDouble(PREF_PREFIX + "ZDISTABOVEFIXED", 0);
      distanceBelowBottomSurface_ = prefs.getDouble(PREF_PREFIX + "ZDISTBELOWBOTTOM", 0);
      distanceAboveTopSurface_ = prefs.getDouble(PREF_PREFIX + "ZDISTABOVETOP", 0);
      spaceMode_ = prefs.getInt(PREF_PREFIX + "SPACEMODE", 0);
      tileOverlap_ = prefs.getDouble(PREF_PREFIX + "TILEOVERLAP", 5);
      //channels
      channelGroup_ = prefs.get(PREF_PREFIX + "CHANNELGROUP", "");
      //This creates a new Object of channelSpecs that is "Owned" by the accquisition
      channels_ = new ChannelSpec(channelGroup_); 
   }
   
   public static double getStoredTileOverlapPercentage() {
      return Magellan.getPrefs().getDouble(PREF_PREFIX + "TILEOVERLAP", 5);
   }
   
   public void storePreferedValues() {
      Preferences prefs = Magellan.getPrefs();
      prefs.put(PREF_PREFIX + "NAME", name_);
      prefs.putBoolean(PREF_PREFIX + "TE", timeEnabled_);
      prefs.putDouble(PREF_PREFIX + "TPI", timePointInterval_);
      prefs.putInt(PREF_PREFIX + "NTP", numTimePoints_);
      prefs.putInt(PREF_PREFIX + "TPIU", timeIntervalUnit_);
      //space
      prefs.putBoolean(PREF_PREFIX +"USECOLLECTIONPLANE", useCollectionPlane_);
      prefs.putDouble(PREF_PREFIX + "ZSTEP", zStep_);
      prefs.putDouble(PREF_PREFIX + "ZSTART", zStart_);
      prefs.putDouble(PREF_PREFIX + "ZEND", zEnd_);
      prefs.putDouble(PREF_PREFIX + "ZDISTBELOWFIXED", distanceBelowFixedSurface_);
      prefs.putDouble(PREF_PREFIX + "ZDISTABOVEFIXED", distanceAboveFixedSurface_);
      prefs.putDouble(PREF_PREFIX + "ZDISTBELOWBOTTOM", distanceBelowBottomSurface_);
      prefs.putDouble(PREF_PREFIX + "ZDISTABOVETOP", distanceAboveTopSurface_);
      prefs.putInt(PREF_PREFIX + "SPACEMODE", spaceMode_);
      prefs.putDouble(PREF_PREFIX + "TILEOVERLAP", tileOverlap_);
      prefs.putBoolean(PREF_PREFIX + "ACQORDER", channelsAtEverySlice_);
      //channels
      prefs.put(PREF_PREFIX + "CHANNELGROUP", channelGroup_);
      //Individual channel settings sotred in ChannelUtils
   }
   
   public String toString() {
      String s = "";
      if (spaceMode_ == CUBOID_Z_STACK) {
         s += "Cuboid volume";
      } else if (spaceMode_ == SURFACE_FIXED_DISTANCE_Z_STACK) {
         s += "Volume within distance from surface";
      } else if (spaceMode_ == VOLUME_BETWEEN_SURFACES_Z_STACK) {
         s += "Volume bounded by surfaces";
      } else if (spaceMode_ == REGION_2D && collectionPlane_ == null) {
         s += "2D plane";
      } else {
         s += "2D along surface";
      }
      int numC = channels_.getNumActiveChannels();
      if (numC > 1) {
         s += " " + numC + " channels";
      }
      if (timeEnabled_) {
         s += " " + numTimePoints_ + " time points";
      }
      return s;
   }

}
