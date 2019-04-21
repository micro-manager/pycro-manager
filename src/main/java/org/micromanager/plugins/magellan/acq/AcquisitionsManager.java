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

import main.java.org.micromanager.plugins.magellan.gui.GUI;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CyclicBarrier;
import javax.swing.JOptionPane;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.Log;

/**
 *
 * @author Henry
 */
public class AcquisitionsManager {

   private List<MagellanGUIAcquisitionSettings> acqSettingsList_ =  Collections.synchronizedList(new ArrayList<MagellanGUIAcquisitionSettings>());
   
   private String[] acqStatus_;
   private GUI gui_;
   private MagellanEngine eng_;
   private volatile boolean running_ = false;
   private Thread managerThread_;
   private volatile MagellanGUIAcquisition currentAcq_;
   private CyclicBarrier acqGroupFinishedBarrier_ = new CyclicBarrier(2);

   public AcquisitionsManager(GUI gui, MagellanEngine eng) {
      gui_ = gui;
      acqSettingsList_.add(new MagellanGUIAcquisitionSettings());
      eng_ = eng;
      eng_.setMultiAcqManager(this);
   }

   public MagellanGUIAcquisitionSettings getAcquisitionSettings(int index) {
      return acqSettingsList_.get(index);
   }

   public int getSize() {
      return acqSettingsList_.size();
   }

   public String getAcquisitionName(int index) {
      return acqSettingsList_.get(index).name_;
   }

   public String setAcquisitionName(int index, String newName) {
      return acqSettingsList_.get(index).name_ = newName;
   }
   
   /**
    * change in position of selected acq
    */
   public int moveUp(int index) {
      if (index == 0) {
         //nothing to do
         return 0;
      } else {
         acqSettingsList_.add(index-1, acqSettingsList_.remove(index));
         return -1;
      }
   }
   
   public int moveDown(int index) {
      if (index == acqSettingsList_.size() - 1) {
         //nothing to do
         return 0;
      } else  {
         acqSettingsList_.add(index+1, acqSettingsList_.remove(index));
         return 1;
      }
   }

   public void addNew() {
      acqSettingsList_.add(new MagellanGUIAcquisitionSettings());
   }

   public void remove(int index) {
      //must always have at least one acquisition
      if (index != -1 && acqSettingsList_.size() > 1) {
         acqSettingsList_.remove(index);       
      }
   }

   public boolean isRunning() {
      return running_;
   }

   public void abort() {
      int result = JOptionPane.showConfirmDialog(null, "Abort current acquisition and cancel future ones?", "Finish acquisitions?", JOptionPane.OK_CANCEL_OPTION);
      if (result != JOptionPane.OK_OPTION) {
         return;
      }

      //stop future acquisitions
      managerThread_.interrupt();
      //abort current parallel acquisition group
      if (currentAcq_ != null) {
         currentAcq_.abort();
      }
      //abort blocks until all the acquisition stuff is closed, so can reset GUI here
      multipleAcquisitionsFinsihed();
   }

   public void runAllAcquisitions() {
      managerThread_ = new Thread(new Runnable() {
         @Override
         public void run() {
            
            //TODO: once an API, disable adding and deleting of acquisitions here
            
            gui_.enableMultiAcquisitionControls(false); //disallow changes while running
            running_ = true;
            acqStatus_ = new String[acqSettingsList_.size()];
            Arrays.fill(acqStatus_, "Waiting");
            gui_.repaint();
            //run acquisitions
            synchronized (acqSettingsList_) {
               for (int acqIndex = 0; acqIndex < acqSettingsList_.size(); acqIndex++) {
                  if (managerThread_.isInterrupted()) {
                     break; //user aborted
                  }
                  acqStatus_[acqIndex] = "Running";
                  try {
                     MagellanGUIAcquisition acq = eng_.runAcquistion(acqSettingsList_.get(acqIndex));
                     acq.is
                  } catch (InterruptedException ex) {
                     //all acquisitions have been aborted
                     break;
                  }
            
                  gui_.acquisitionSettingsChanged(); //so that the available data thing updates
                  gui_.repaint();
               }
            }
            multipleAcquisitionsFinsihed();
         }
      }, "Multiple acquisition manager thread");
      managerThread_.start();
   }

   private void multipleAcquisitionsFinsihed() {
      //reset barier for a new round
      acqGroupFinishedBarrier_ = new CyclicBarrier(2);
      //update GUI
      running_ = false;
      acqStatus_ = null;
      gui_.enableMultiAcquisitionControls(true);
   }

   public void markAsAborted(MagellanGUIAcquisitionSettings settings) {
      if (acqStatus_ != null) {
         acqStatus_[acqSettingsList_.indexOf(settings)] = "Aborted";
         gui_.repaint();
      }
   }

   /**
    * Called by parallel acquisition group when it is finished so that manager
    * knows to move onto next one
    */
   public void parallelAcqGroupFinished() {
      try {
         if (managerThread_.isAlive()) {
            acqGroupFinishedBarrier_.await();
         } //otherwise it was aborted, so nothing to do        
      } catch (Exception ex) {
         //exceptions should never happen because this is always the second await to be called
         Log.log("Unexpected exception: multi acq manager interrupted or barrier broken");
         ex.printStackTrace();
         throw new RuntimeException();
      }
      currentAcq_ = null;
   }

   public String getAcquisitionDescription(int index) {
      return acqSettingsList_.get(index).toString();
   }

   private void validateSettings(MagellanGUIAcquisitionSettings settings) throws Exception {
      //space
      //non null surface
      if ((settings.spaceMode_ == MagellanGUIAcquisitionSettings.REGION_2D || settings.spaceMode_ == MagellanGUIAcquisitionSettings.CUBOID_Z_STACK)
              && settings.footprint_ == null) {
         Log.log("Error: No surface or region selected for " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK && settings.fixedSurface_ == null) {
         Log.log("Error: No surface selected for " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK && settings.footprint_ == null) {
         Log.log("Error: No xy footprint selected for " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK
              && (settings.topSurface_ == null || settings.bottomSurface_ == null)) {
         Log.log("Error: No surface selected for " + settings.name_, true);
         throw new Exception();
      }
      //correct coordinate devices--XY
      if ((settings.spaceMode_ == MagellanGUIAcquisitionSettings.REGION_2D || settings.spaceMode_ == MagellanGUIAcquisitionSettings.CUBOID_Z_STACK)
              && !settings.footprint_.getXYDevice().equals(Magellan.getCore().getXYStageDevice())) {
         Log.log("Error: XY device for surface/grid does match XY device in MM core in " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK
              && !settings.fixedSurface_.getXYDevice().equals(Magellan.getCore().getXYStageDevice())) {
         Log.log("Error: XY device for surface does match XY device in MM core in " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK
              && (!settings.topSurface_.getXYDevice().equals(Magellan.getCore().getXYStageDevice())
              || !settings.bottomSurface_.getXYDevice().equals(Magellan.getCore().getXYStageDevice()))) {
         Log.log("Error: XY device for surface does match XY device in MM core in " + settings.name_, true);
         throw new Exception();
      }
      //correct coordinate device--Z
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.SURFACE_FIXED_DISTANCE_Z_STACK
              && !settings.fixedSurface_.getZDevice().equals(Magellan.getCore().getFocusDevice())) {
         Log.log("Error: Z device for surface does match Z device in MM core in " + settings.name_, true);
         throw new Exception();
      }
      if (settings.spaceMode_ == MagellanGUIAcquisitionSettings.VOLUME_BETWEEN_SURFACES_Z_STACK
              && (!settings.topSurface_.getZDevice().equals(Magellan.getCore().getFocusDevice())
              || !settings.bottomSurface_.getZDevice().equals(Magellan.getCore().getFocusDevice()))) {
         Log.log("Error: Z device for surface does match Z device in MM core in " + settings.name_, true);
         throw new Exception();
      }

      //channels
//       if (settings.channels_.isEmpty()) {
//           Log.log("Error: no channels selected for " + settings.name_);
//           throw new Exception();
//       }
   }

}
