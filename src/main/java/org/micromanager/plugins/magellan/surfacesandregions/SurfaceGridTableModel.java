/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package main.java.org.micromanager.plugins.magellan.surfacesandregions;

import java.util.logging.Level;
import java.util.logging.Logger;
import javax.swing.table.AbstractTableModel;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.misc.NumberUtils;

/**
 *
 * @author henrypinkard
 */
public class SurfaceGridTableModel extends AbstractTableModel {

   private final String[] COLUMNS = {"Type", "Name", "XY padding (um)", "Z Device", "# Positions"};

   private SurfaceGridManager manager_;

   public SurfaceGridTableModel(SurfaceGridManager manager) {
      manager_ = manager;
   }

   @Override
   public int getRowCount() {
      return manager_.getNumberOfSurfaces() + manager_.getNumberOfGrids();
   }

   @Override
   public String getColumnName(int index) {
      return COLUMNS[index];
   }

   @Override
   public int getColumnCount() {
      return COLUMNS.length;
   }

   @Override
   public boolean isCellEditable(int rowIndex, int colIndex) {
      if (colIndex == 1) {
         return true;
      } else if (colIndex == 2 && manager_.getSurfaceOrGrid(rowIndex) instanceof SurfaceInterpolator) {
         return true; // only surfaces have XY padding
      }
      return false;
   }

   @Override
   public void setValueAt(Object value, int row, int col) {
      if (col == 1) {
         try {
            manager_.rename(row, (String) value);
         } catch (Exception ex) {
            Log.log("Name already taken by existing Surface/Grid", true);
         }
      } else if (col == 2 && manager_.getSurfaceOrGrid(row) instanceof SurfaceInterpolator) {
         ((SurfaceInterpolator)manager_.getSurfaceOrGrid(row)).setXYPadding(NumberUtils.parseDouble((String) value));
      }
   }

   @Override
   public Object getValueAt(int rowIndex, int columnIndex) {
//         private final String[] COLUMNS = {"Type", "Name", "XY padding (um)", "Z Device", "# Positions",
//      "# Rows", "# Cols", "Width (um)", "Height (um)"};
         
      XYFootprint surfaceOrGird = manager_.getSurfaceOrGrid(rowIndex);
      if (columnIndex == 0) {
         return manager_.getSurfaceOrGrid(rowIndex) instanceof SurfaceInterpolator ? "Surface"  : "Grid";
      } else if (columnIndex == 1) {         
         return manager_.getSurfaceOrGrid(rowIndex).getName();
      } else if (columnIndex == 2) {
         if (manager_.getSurfaceOrGrid(rowIndex) instanceof MultiPosGrid) {
            return 0;
         }
         return ((SurfaceInterpolator) manager_.getSurfaceOrGrid(rowIndex)).getXYPadding();
      } else if (columnIndex == 3) {
         if (manager_.getSurfaceOrGrid(rowIndex) instanceof MultiPosGrid) {
            return "N/A";
         }
         return ((SurfaceInterpolator) manager_.getSurfaceOrGrid(rowIndex)).getZDevice();
      } else {
         try {
            return  manager_.getSurfaceOrGrid(rowIndex).getXYPositionsNoUpdate().size();
         } catch (InterruptedException ex) {
            Log.log(ex);
            return null;
         }

      } 
   }

}
