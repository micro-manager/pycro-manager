package org.micromanager.explore.gui;

import org.micromanager.explore.ExploreAcquisition;
import org.micromanager.explore.XYTiledAcqViewerStorageAdapater;
import org.micromanager.ndviewer.api.CanvasMouseListenerInterface;
import org.micromanager.ndviewer.main.NDViewer;

import javax.swing.*;
import java.awt.*;
import java.awt.event.MouseEvent;
import java.awt.event.MouseWheelEvent;
import java.util.function.Consumer;

/**
 *
 * @author henrypinkard
 */
public class ExploreMouseListener implements CanvasMouseListenerInterface {

   private static final int DELETE_SURF_POINT_PIXEL_TOLERANCE = 10;
   private static final int MOUSE_WHEEL_ZOOM_INTERVAL_MS = 100;

   private static final double ZOOM_FACTOR_MOUSE = 1.4;

   //all these are volatile because they are accessed by overlayer
   private volatile Point mouseDragStartPointLeft_;
   private volatile Point mouseDragStartPointRight_;
   private volatile Point currentMouseLocation_;
   private volatile long lastMouseWheelZoomTime_ = 0;
   private volatile boolean mouseDragging_ = false;

   private ExploreAcquisition acq_;
   private NDViewer viewer_;

   protected volatile Point exploreStartTile_;
   protected volatile Point exploreEndTile_;
   protected Consumer<String> logger_;
   protected boolean exploreActive_;
   private XYTiledAcqViewerStorageAdapater adapater_;

   /**
    * Mouse Listener class for paning zooming, and clicking to explore tiles
    * @param acquisition
    * @param viewer
    * @param logger
    */
   public ExploreMouseListener(XYTiledAcqViewerStorageAdapater adapter,
                               ExploreAcquisition acquisition, NDViewer viewer,
                               Consumer<String> logger) {
      acq_ = acquisition;
      viewer_ = viewer;
      logger_ = logger;
      adapater_ = adapter;
      exploreActive_ = true;
   }

   public void setExploreActive(boolean active) {
      exploreActive_ = active;
   }

   @Override
   public void mouseWheelMoved(MouseWheelEvent mwe) {
      long currentTime = System.currentTimeMillis();
      if (currentTime - lastMouseWheelZoomTime_ > MOUSE_WHEEL_ZOOM_INTERVAL_MS) {
         lastMouseWheelZoomTime_ = currentTime;
         if (mwe.getWheelRotation() < 0) {
            viewer_.zoom(1 / ZOOM_FACTOR_MOUSE, currentMouseLocation_); // zoom in?
         } else if (mwe.getWheelRotation() > 0) {
            viewer_.zoom(ZOOM_FACTOR_MOUSE, currentMouseLocation_); //zoom out
         }
      }
   }

   @Override
   public void mouseMoved(MouseEvent e) {
      currentMouseLocation_ = e.getPoint();
      if (exploreActive_) {
         viewer_.redrawOverlay();
      }
   }

   @Override
   public void mousePressed(MouseEvent e) {
      //to make zoom respond properly when switching between windows
      viewer_.getCanvasJPanel().requestFocusInWindow();
      if (SwingUtilities.isRightMouseButton(e)) {
         //clear potential explore region
         exploreEndTile_ = null;
         exploreStartTile_ = null;
         mouseDragStartPointRight_ = e.getPoint();
      } else if (SwingUtilities.isLeftMouseButton(e)) {
         mouseDragStartPointLeft_ = e.getPoint();
      }
      viewer_.redrawOverlay();
   }

   @Override
   public void mouseReleased(MouseEvent e) {
      mouseReleasedActions(e);
      mouseDragStartPointLeft_ = null;
      mouseDragStartPointRight_ = null;
      viewer_.redrawOverlay();
   }

   @Override
   public void mouseEntered(MouseEvent e) {
      if (exploreActive_) {
         viewer_.redrawOverlay();
      }
   }

   @Override
   public void mouseExited(MouseEvent e) {
      currentMouseLocation_ = null;
      if (exploreActive_) {
         viewer_.redrawOverlay();
      }
   }

   protected void mouseReleasedActions(MouseEvent e) {
      if (exploreActive_ && SwingUtilities.isLeftMouseButton(e)) {
         Point p2 = e.getPoint();
         if (exploreStartTile_ != null) {
            //create events to acquire one or more tiles
            acq_.acquireTiles(
                    exploreStartTile_.y, exploreStartTile_.x, exploreEndTile_.y, exploreEndTile_.x);
            exploreStartTile_ = null;
            exploreEndTile_ = null;
         } else {
            //find top left row and column and number of columns spanned by drage event
            exploreStartTile_ = adapater_.getTileIndicesFromDisplayedPixel(
                    mouseDragStartPointLeft_.x, mouseDragStartPointLeft_.y);
            exploreEndTile_ = adapater_.getTileIndicesFromDisplayedPixel(p2.x, p2.y);
         }
         viewer_.redrawOverlay();
      }
      mouseDragging_ = false;
      viewer_.redrawOverlay();
   }

   @Override
   public void mouseDragged(MouseEvent e) {
      currentMouseLocation_ = e.getPoint();
      mouseDraggedActions(e);
   }

   private void mouseDraggedActions(MouseEvent e) {
      Point currentPoint = e.getPoint();
      mouseDragging_ = true;
      if (SwingUtilities.isRightMouseButton(e)) {
         //pan
         viewer_.pan(mouseDragStartPointRight_.x - currentPoint.x,
               mouseDragStartPointRight_.y - currentPoint.y);
         mouseDragStartPointRight_ = currentPoint;
      }
      viewer_.redrawOverlay();
   }

   @Override
   public void mouseClicked(MouseEvent e) {
   }

   public Point getExploreStartTile() {
      return exploreStartTile_;
   }

   public Point getExploreEndTile() {
      return exploreEndTile_;
   }

   public Point getMouseDragStartPointLeft() {
      return mouseDragStartPointLeft_;
   }

   public Point getCurrentMouseLocation() {
      return currentMouseLocation_;
   }

}
