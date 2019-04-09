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

package main.java.org.micromanager.plugins.magellan.gui;

import javax.swing.DefaultComboBoxModel;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridManager;

/**
 *
 * @author Henry
 */
public class SurfaceGridComboBoxModel extends DefaultComboBoxModel {
   
   private SurfaceGridManager manager_;
   private Object selectedItem_ = null;
   private final boolean surfacesOnly_, gridsOnly_;

   public SurfaceGridComboBoxModel(boolean surfacesOnly, boolean gridsOnly)  {
      manager_ = SurfaceGridManager.getInstance();
      surfacesOnly_ = surfacesOnly;
      gridsOnly_ = gridsOnly;
   }

   @Override
   public Object getSelectedItem() {
      return selectedItem_;
   }

   @Override
   public void setSelectedItem(Object anItem) {
     selectedItem_ = anItem;
   }

   @Override
   public int getSize() {
      if (surfacesOnly_) {
         return manager_.getNumberOfSurfaces();
      }
      if (gridsOnly_) {
         return manager_.getNumberOfGrids();
      }
      return manager_.getNumberOfGrids() + manager_.getNumberOfSurfaces(); 
   }

   @Override
   public Object getElementAt(int index) {
      if (index == -1) {
         return null;
      }     
      if (surfacesOnly_) {
         return manager_.getSurface(index);
      } else {
         return manager_.getSurfaceOrGrid(index);
      }
   }

   public void update() {
      super.fireContentsChanged(manager_, -1, -1);
   }
   
}
