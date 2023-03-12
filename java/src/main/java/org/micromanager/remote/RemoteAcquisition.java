/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import org.micromanager.acqj.main.Acquisition;
import org.micromanager.ndtiffstorage.NDTiffAPI;
import org.micromanager.ndviewer.api.NDViewerAcqInterface;
import org.micromanager.ndviewer.api.NDViewerAPI;

/**
 * Class that serves as the java counterpart to a python acquisition
 *
 *
 * @author henrypinkard
 */
public class RemoteAcquisition extends Acquisition
        implements NDViewerAcqInterface, PycroManagerCompatibleAcq {

   private RemoteEventSource eventSource_;

   public RemoteAcquisition(RemoteEventSource eventSource, RemoteViewerStorageAdapter sink, boolean debug) {
      super(sink);
      this.setDebugMode(debug);
      eventSource_ = eventSource;
      eventSource.setAcquisition(this);
   }

   @Override
   public int getEventPort() {
      return eventSource_.getPort();
   }


   @Override
   public void abort() {
      super.abort();
      eventSource_.abort();
   }


   @Override
   public void abort(Exception e) {
      super.abort(e);
      eventSource_.abort();
   }


   @Override
   public boolean isFinished() {
      if (getDataSink() != null) {
         return eventSource_.isFinished() && areEventsFinished() && getDataSink().isFinished();
      }
      return eventSource_.isFinished() && areEventsFinished();
   }

   @Override
   public NDTiffAPI getStorage() {
      return ((RemoteViewerStorageAdapter) dataSink_).getStorage();
   }
}
