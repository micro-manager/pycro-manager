package org.micromanager.remote;

import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.NDViewerAPI;

/**
 * This interface enables acquisitions created on the Java side to work with different
 * components of pycro-manager. For example, enabling opening of their (NDTiff only)
 * data directly on the Python side once it is written so it can be analyzed/displayed
 */
public interface PycroManagerCompatibleAcq {

   public NDTiffAPI getStorage();

   /**
    * Get the port over which the acquisition accepts acquisition events, or -1 if this
    * is not available
    * @return
    */
   public int getEventPort();

   /**
    * Get reference to NDViewer displaying this acquisitions data
    */
   public NDViewerAPI getViewer();

}
