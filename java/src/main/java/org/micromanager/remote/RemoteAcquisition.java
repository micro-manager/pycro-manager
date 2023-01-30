/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.ViewerAcquisitionInterface;
import org.micromanager.ndviewer.api.ViewerInterface;

/**
 * Class that serves as the java counterpart to a python acquisition
 *
 *
 * @author henrypinkard
 */
public class RemoteAcquisition extends Acquisition implements ViewerAcquisitionInterface {

   private RemoteEventSource eventSource_;

   public RemoteAcquisition(RemoteEventSource eventSource, RemoteViewerStorageAdapter sink, boolean debug) {
      super(sink);
      this.setDebugMode(debug);
      eventSource_ = eventSource;
      eventSource.setAcquisition(this);
   }

   /**
    * Called by python side
    */
   public int getEventPort() {
      return eventSource_.getPort();
   }

   /**
    * Called by python side
    */
   public ViewerInterface getViewer() {
      return ((RemoteViewerStorageAdapter) getDataSink()).getViewer();
   }

   @Override
   public void abort() {
      super.abort();
      eventSource_.abort();
   }

   @Override
   public void togglePaused() {
      setPaused(!isPaused());
   }


   @Override
   public void abort(Exception e) {
      super.abort(e);
      eventSource_.abort();
   }


   @Override
   public boolean isFinished() {
      if (getDataSink() != null) {
         return eventSource_.isFinished() && getDataSink().isFinished();
      }
      return eventSource_.isFinished();
   }

}
