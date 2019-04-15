/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package main.java.org.micromanager.plugins.magellan.imagedisplay;

import java.awt.geom.Point2D;
import java.util.HashMap;
import java.util.TreeMap;
import javax.swing.table.AbstractTableModel;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.misc.NumberUtils;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.MultiPosGrid;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridListener;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridManager;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceInterpolator;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.XYFootprint;

/**
 *
 * @author henrypinkard
 */
public class DisplayWindowSurfaceGridTableModel extends AbstractTableModel implements SurfaceGridListener {

   private final String[] COLUMNS = {"Show", "Type", "Name"};
   //maybe, "Z Device"
   private HashMap<XYFootprint, Boolean> showSurfaceOrGridMap = new HashMap<XYFootprint, Boolean>();

   private SurfaceGridManager manager_ = SurfaceGridManager.getInstance();

   public DisplayWindowSurfaceGridTableModel() {
      manager_.registerSurfaceGridListener(this);
      for (int i = 0; i < manager_.getNumberOfGrids() + manager_.getNumberOfSurfaces(); i++) {
         showSurfaceOrGridMap.put(manager_.getSurfaceOrGrid(i), Boolean.TRUE);
      }
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
      if (colIndex == 0 || colIndex == 2) {
         return true;
      } else if (colIndex == 3 && manager_.getSurfaceOrGrid(rowIndex) instanceof SurfaceInterpolator) {
         return true; // only surfaces have XY padding
      }
      return false;
   }

   @Override
   public void setValueAt(Object value, int row, int col) {
      if (col == 0) {
         showSurfaceOrGridMap.put(manager_.getSurfaceOrGrid(row), !showSurfaceOrGridMap.get(manager_.getSurfaceOrGrid(row)));
      } else if (col == 2) { 
         try {
            manager_.rename(row, (String) value);
         } catch (Exception ex) {
            Log.log("Name already taken by existing Surface/Grid", true);
         }
      } 
   }

   @Override
   public Object getValueAt(int rowIndex, int columnIndex) {
         
      XYFootprint surfaceOrGird = manager_.getSurfaceOrGrid(rowIndex);
      if (columnIndex == 0) {
         return showSurfaceOrGridMap.get(surfaceOrGird);
      } else if (columnIndex == 1) {
         return manager_.getSurfaceOrGrid(rowIndex) instanceof SurfaceInterpolator ? "Surface"  : "Grid";
      } else  {         
         return manager_.getSurfaceOrGrid(rowIndex).getName();
      } 
   }
   
      @Override
   public Class getColumnClass(int columnIndex) {
      if (columnIndex == 0) {
         return Boolean.class;
      } else if (columnIndex == 1) {
         return String.class;
      } else  {
         return String.class;
      } 
   }

   @Override
   public void SurfaceOrGridChanged(XYFootprint f) {
      this.fireTableDataChanged();
   }

   @Override
   public void SurfaceOrGridDeleted(XYFootprint f) {
      showSurfaceOrGridMap.remove(f);
      this.fireTableDataChanged();
   }

   @Override
   public void SurfaceOrGridCreated(XYFootprint f) {
      showSurfaceOrGridMap.put(f, Boolean.TRUE);
      this.fireTableDataChanged();
   }

   @Override
   public void SurfaceOrGridRenamed(XYFootprint f) {
      this.fireTableDataChanged();
   }

   public void shutdown() {
      manager_.removeSurfaceGridListener(this);
   }

   public SurfaceInterpolator addNewSurface() {
      return manager_.addNewSurface();
   }

   public MultiPosGrid newGrid(int rows, int cols, Point2D.Double center) {
      return manager_.addNewGrid(rows, cols, center);
   }
}
