package org.micromanager.explore.gui;

import java.awt.*;

public interface ExploreMouseListenerAPI {

   public Point getExploreStartTile();

   public Point getExploreEndTile();

   public Point getMouseDragStartPointLeft();

   public Point getCurrentMouseLocation();

}
