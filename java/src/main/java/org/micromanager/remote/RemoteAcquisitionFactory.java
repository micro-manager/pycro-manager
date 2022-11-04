/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import mmcorej.CMMCore;
import org.micromanager.acqj.internal.Engine;

/**
 *
 * @author henrypinkard
 */
public class RemoteAcquisitionFactory {
   
   private Engine eng_;

   /////////////////////////////////////////////////////////////////
   /////////   These methods are called by the Python side /////////
   /////////////////////////////////////////////////////////////////
   public RemoteAcquisitionFactory(CMMCore core) {
      eng_ = Engine.getInstance();
      if (eng_ == null) {
         eng_ = new Engine(core);
      }
   }

   public XYTiledRemoteAcquisition createTiledAcquisition(String dir, String name, boolean showViewer,
                                              boolean xyTiled, int tileOverlapX, int tileOverlapY, int maxResLevel,
                                              int savingQueueSize, boolean debug) {
      RemoteEventSource eventSource = new RemoteEventSource();
      RemoteViewerStorageAdapter adapter = null;
      if (name != null && dir != null) {
         // Saving to disk
         adapter = new RemoteViewerStorageAdapter(showViewer, dir, name, xyTiled, tileOverlapX, tileOverlapY,
                 maxResLevel == -1 ? null : maxResLevel, savingQueueSize);

      }
      return new XYTiledRemoteAcquisition(eventSource, adapter, debug);
   }

   public RemoteAcquisition createAcquisition(String dir, String name, boolean showViewer,
                                              int savingQueueSize, boolean debug) {
      RemoteEventSource eventSource = new RemoteEventSource();
      RemoteViewerStorageAdapter adapter = null;
      if (name != null && dir != null) {
         // Saving to disk
         adapter = new RemoteViewerStorageAdapter(showViewer, dir, name, false, 0,0,
                 null, savingQueueSize);

      }
      return new RemoteAcquisition(eventSource, adapter, debug);
   }

   
}
