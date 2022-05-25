/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.multiresstorage.StorageAPI;
import org.micromanager.ndviewer.api.ViewerAcquisitionInterface;

/**
 * Class that serves as the java counterpart to a python acquisition
 *
 *
 * @author henrypinkard
 */
public class RemoteAcquisition extends Acquisition
        implements AcquisitionAPI, ViewerAcquisitionInterface {

   private RemoteEventSource eventSource_;

   public RemoteAcquisition(RemoteEventSource eventSource, RemoteViewerStorageAdapter sink, boolean debug) {
      super(sink);
      this.setDebugMode(debug);
      if (dataSink_ != null && ((RemoteViewerStorageAdapter)dataSink_).isXYTiled()) {
         initialize(((RemoteViewerStorageAdapter) dataSink_).getOverlapX(),
                 ((RemoteViewerStorageAdapter) dataSink_).getOverlapY());
      } else {
         initialize();
      }
      eventSource_ = eventSource;
      eventSource.setAcquisition(this);
   }

   public StorageAPI getStorage() {
      return dataSink_ == null ? null : ((RemoteViewerStorageAdapter) dataSink_).getStorage();
   }

   /**
    * Called by python side
    * @return
    */
   public RemoteStorageMonitor getStorageMonitor() {
      return ((RemoteViewerStorageAdapter) dataSink_).getStorageMonitor();
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
   public boolean isFinished() {
      if (dataSink_ != null) {
         return eventSource_.isFinished() && dataSink_.isFinished();
      }
      return eventSource_.isFinished();
   }

   @Override
   public void addToSummaryMetadata(JSONObject summaryMetadata) {

   }

   @Override
   public void addToImageMetadata(JSONObject tags) {

   }


}
