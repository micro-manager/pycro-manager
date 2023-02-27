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

package org.micromanager.explore;

import org.micromanager.explore.gui.ExploreMouseListener;
import org.micromanager.ndviewer.api.OverlayerPlugin;
import org.micromanager.ndviewer.overlay.Overlay;
import org.micromanager.ndviewer.overlay.Roi;
import org.micromanager.ndviewer.overlay.TextRoi;

import java.awt.*;
import java.awt.geom.Point2D;
import java.util.HashMap;
import java.util.concurrent.LinkedBlockingQueue;

/**
 * Class that encapsulates calculation of overlays for DisplayPlus.
 */
public class ExploreOverlayer implements OverlayerPlugin {
   private static final Color LIGHT_BLUE = new Color(200, 200, 255);
   private static final Color TRANSPARENT_BLUE = new Color(0, 0, 255, 100);
   private static final Color TRANSPARENT_GREEN = new Color(0, 255, 0, 100);
   private static final Color TRANSPARENT_MAGENTA = new Color(255, 0, 255, 100);

   private XYTiledAcqViewerStorageAdapater viewerStorageAdapter_;
   private ExploreMouseListener mouseListener_;
   private boolean active_ = true;

   public ExploreOverlayer(XYTiledAcqViewerStorageAdapater adapater, ExploreMouseListener mouseListener) {
      viewerStorageAdapter_ = adapater;
      mouseListener_ = mouseListener;

   }



   public void setActive(boolean b) {
      active_ = b;
   }

   @Override
   public void drawOverlay(Overlay defaultOverlay,
                           Point2D.Double displayImageSize,
           double downsampleFactor, Graphics g, HashMap<String, Object> axes,
           double magnification, Point2D.Double viewOffset) throws InterruptedException {
      if (active_) {
         Overlay easyOverlay = new Overlay();
         //Create a simple overlay and send it to EDT for display
         addExploreToOverlay(easyOverlay, magnification, g, displayImageSize);
      }
   }



   public void addExploreToOverlay(Overlay overlay, double magnification, Graphics g,
           Point2D.Double displayImageSize) {
      Point currentMouseLocation = mouseListener_.getCurrentMouseLocation();
      if (mouseListener_.getExploreEndTile() != null) {
         //draw explore tiles waiting to be confirmed with a click
         highlightTilesOnOverlay(overlay, Math.min(
               mouseListener_.getExploreEndTile().y,
                 mouseListener_.getExploreStartTile().y),
                 Math.max(mouseListener_.getExploreEndTile().y,
                         mouseListener_.getExploreStartTile().y),
                 Math.min(mouseListener_.getExploreEndTile().x,
                         mouseListener_.getExploreStartTile().x),
                 Math.max(mouseListener_.getExploreEndTile().x,
                         mouseListener_.getExploreStartTile().x),
                 TRANSPARENT_MAGENTA, magnification);
         addTextBox(new String[]{"Left click again to confirm acquire", "Right click to cancel"},
               overlay, g, displayImageSize);
      } else if (mouseListener_.getMouseDragStartPointLeft() != null) {
         //highlight multiple tiles when mouse dragging    
         Point dragStart = mouseListener_.getMouseDragStartPointLeft();
         Point p2Tiles = viewerStorageAdapter_.getTileIndicesFromDisplayedPixel(currentMouseLocation.x,
               currentMouseLocation.y);
         Point p1Tiles = viewerStorageAdapter_.getTileIndicesFromDisplayedPixel(dragStart.x, dragStart.y);
         highlightTilesOnOverlay(overlay, Math.min(p1Tiles.y, p2Tiles.y),
               Math.max(p1Tiles.y, p2Tiles.y),
               Math.min(p1Tiles.x, p2Tiles.x),
               Math.max(p1Tiles.x, p2Tiles.x),
               TRANSPARENT_BLUE, magnification);
      } else if (currentMouseLocation != null) {
         //draw single highlighted tile under mouse
         Point coords = viewerStorageAdapter_.getTileIndicesFromDisplayedPixel(
                 currentMouseLocation.x, currentMouseLocation.y);
         highlightTilesOnOverlay(overlay, coords.y, coords.y, coords.x, coords.x,
                 TRANSPARENT_BLUE, magnification); //highligth single tile
      } else if (!viewerStorageAdapter_.anythingAcquired()) {

         String[] text = {"Explore mode controls:", "",
               "Left click or left click and drag to select tiles",
            "Left click again to confirm", "Right click and drag to pan",
               "+/- keys or mouse wheel to zoom in/out"};
         addTextBox(text, overlay, g, displayImageSize);
      }
      //      always draw tiles waiting to be acquired
      LinkedBlockingQueue<ExploreAcquisition.ExploreTileWaitingToAcquire> tiles
              = viewerStorageAdapter_.getTilesWaitingToAcquireAtVisibleSlice();
      if (tiles != null) {
         for (ExploreAcquisition.ExploreTileWaitingToAcquire t : tiles) {
            highlightTilesOnOverlay(overlay, t.row, t.row, t.col, t.col,
                  TRANSPARENT_GREEN, magnification);
         }
      }
   }

   private void addTextBox(String[] text, Overlay overlay, Graphics g,
                           Point2D.Double displayImageSize) {
      int fontSize = 12;
      Font font = new Font("Arial", Font.BOLD, fontSize);
      float lineHeight = 0;
      float textWidth = 0;
      for (String line : text) {
         lineHeight = Math.max(lineHeight,
               g.getFontMetrics(font).getLineMetrics(line, g).getHeight());
         textWidth = Math.max(textWidth, g.getFontMetrics().stringWidth(line));
      }
      float textHeight = lineHeight * text.length;
      //10 pixel border 
      int border = 10;
      int roiWidth = (int) ((textWidth + 2 * border) * 1.3); //add 50 as a hack for windows
      int roiHeight = (int) (textHeight + 2 * border);
      Roi rectangle = new Roi(displayImageSize.x / 2 - roiWidth / 2,
              displayImageSize.y / 2 - roiHeight / 2, roiWidth, roiHeight);
      rectangle.setStrokeWidth(3f);
      rectangle.setFillColor(LIGHT_BLUE);
      overlay.add(rectangle);

      for (int i = 0; i < text.length; i++) {
         TextRoi troi = new TextRoi(displayImageSize.x / 2 - roiWidth / 2 + border,
                 displayImageSize.y / 2 - roiHeight / 2 + border + lineHeight * i, text[i], font);
         troi.setStrokeColor(Color.black);
         overlay.add(troi);
      }
   }

   private void highlightTilesOnOverlay(Overlay base, long row1, long row2, long col1,
           long col2, Color color, double magnification) {
      Point topLeft = viewerStorageAdapter_.getDisplayedPixel(row1, col1);
      int width = (int) Math.round(viewerStorageAdapter_.getDisplayTileWidth()
            * (col2 - col1 + 1) * magnification);
      int height = (int) Math.round(viewerStorageAdapter_.getDisplayTileHeight()
            * (row2 - row1 + 1) * magnification);
      Roi rect = new Roi(topLeft.x, topLeft.y, width, height);
      rect.setFillColor(color);
      base.add(rect);
   }

}
