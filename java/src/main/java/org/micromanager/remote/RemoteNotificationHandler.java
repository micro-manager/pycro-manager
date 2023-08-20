/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import mmcorej.org.json.JSONException;
import org.micromanager.acqj.api.AcqNotificationListener;
import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.acqj.main.AcqNotification;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.internal.zmq.ZMQPushSocket;
import org.micromanager.ndtiffstorage.IndexEntryData;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingDeque;

/**
 * A class that broadcasts information about images that have finsihed saving to disk
 * @author henrypinkard
 */
public class RemoteNotificationHandler implements AcqNotificationListener {

   private ZMQPushSocket<AcqNotification> pushSocket_;
   private ExecutorService executor_ = Executors.newSingleThreadExecutor((Runnable r) -> {
      return new Thread(r, "Remote Event Source thread");
   });
   private LinkedBlockingDeque<AcqNotification> notifications_ = new LinkedBlockingDeque<AcqNotification>();

   /**
    * Called by python side
    */
   public RemoteNotificationHandler(AcquisitionAPI acq) {
      acq.addAcqNotificationListener(this);
      pushSocket_ = new ZMQPushSocket<AcqNotification>(
           t -> {
              try {
                 return t.toJSON();
              } catch (JSONException e) {
                 throw new RuntimeException("Problem with notification socket");
              }
           });
   }

   /**
    * Start pushing out the indices to the other side
    */
   public void start() {
      //constantly poll the socket for more event sequences to submit
      executor_.submit(() -> {
         while (true) {
            AcqNotification e = null;
            try {
               e = notifications_.takeFirst();
            } catch (InterruptedException ex) {
               // this should never happen
               ex.printStackTrace();
               throw new RuntimeException(ex);
            }

            pushSocket_.push(e);
            if (e.isAcquisitionFinishedNotification()) {
               return ;
            }
         }
      });
   }

   @Override
   public void postNotification(AcqNotification n) {
      notifications_.add(n);
   }

   /**
    * Called by the python side to signal that the final shutdown signal has been received
    * and that the push socket can be closed
    */
   public void notificationHandlingComplete() {
      executor_.shutdown();
      pushSocket_.close();
   }

   public int getPort() {
      return pushSocket_.getPort();
   }

}
