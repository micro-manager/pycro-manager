/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.main.XYTiledAcquisition;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.ViewerAcquisitionInterface;

/**
 * Class that serves as the java counterpart to a python acquisition
 *
 *
 * @author henrypinkard
 */
public class XYTiledRemoteAcquisition extends XYTiledAcquisition implements AcquisitionAPI, ViewerAcquisitionInterface {

   private RemoteEventSource eventSource_;

   public XYTiledRemoteAcquisition(RemoteEventSource eventSource, RemoteViewerStorageAdapter sink, boolean debug) {
      super(sink, sink.getOverlapX(), sink.getOverlapY());
      setDebugMode(debug);
      eventSource_ = eventSource;
      eventSource.setAcquisition(this);
   }

   public NDTiffAPI getStorage() {
      return getDataSink() == null ? null : ((RemoteViewerStorageAdapter) getDataSink()).getStorage();
   }


   /**
    * Called by python side
    */
   public int getEventPort() {
      return eventSource_.getPort();
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
