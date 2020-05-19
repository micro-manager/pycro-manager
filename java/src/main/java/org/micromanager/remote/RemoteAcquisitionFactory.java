/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import mmcorej.CMMCore;
import org.micromanager.acqj.internal.acqengj.Engine;

/**
 *
 * @author henrypinkard
 */
public class RemoteAcquisitionFactory {
   
   private Engine eng_;
   
   public RemoteAcquisitionFactory(CMMCore core) {
      eng_ = Engine.getInstance();
      if (eng_ == null) {
         eng_ = new Engine(core);
      }
   }

   public RemoteAcquisition createAcquisition() {
      RemoteEventSource eventSource = new RemoteEventSource();
      return new RemoteAcquisition(eventSource,null);
   }
   
   public RemoteAcquisition createAcquisition(String dir, String name, boolean showViewer) {
      RemoteEventSource eventSource = new RemoteEventSource();
      RemoteViewerStorageAdapter adapter = new RemoteViewerStorageAdapter(showViewer, dir, name);
      return new RemoteAcquisition(eventSource, adapter);
   }
   
   
}
