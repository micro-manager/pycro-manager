package org.micromanager.remote;

import org.micromanager.ndviewer.api.NDViewerAPI;

public interface PycroManagerCompatibleUI {

   /**
    * Get reference to NDViewer displaying this acquisitions data
    */
   public NDViewerAPI getViewer();
}
