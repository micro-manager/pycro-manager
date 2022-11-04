/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.acqj.main.AcquisitionEvent;
import org.micromanager.internal.zmq.ZMQPullSocket;

import javax.swing.*;

/**
 * A source of acquisition events that comes from elsewhere via a ZMQ pull socket
 * @author henrypinkard
 */
public class RemoteEventSource {

   private ZMQPullSocket<List<AcquisitionEvent>> pullSocket_;
   private Acquisition acq_;
   private ExecutorService executor_ = Executors.newSingleThreadExecutor((Runnable r) -> {
      return new Thread(r, "Remote Event Source thread");
   });

   public RemoteEventSource() {
      pullSocket_ = new ZMQPullSocket<>(
              t -> {
                 try {
                    List<AcquisitionEvent> eventList = new ArrayList<>();
                    JSONArray events = t.getJSONArray("events");
                    for (int i = 0; i < events.length(); i++) {
                       JSONObject e = events.getJSONObject(i);
                       eventList.add(AcquisitionEvent.fromJSON(e, acq_));
                    }
                    return eventList;
                 } catch (JSONException ex) {
                    throw new RuntimeException("Incorrect format for acquisitio event");
                 }
              });
      //constantly poll the socket for more event sequences to submit
      executor_.submit(() -> {
         while (true) {
            try {
               List<AcquisitionEvent> eList = pullSocket_.next();
               boolean finished = eList.get(eList.size() - 1).isAcquisitionFinishedEvent();
               Future result = acq_.submitEventIterator(eList.iterator());
               result.get(); //propogate any exceptions
               if (finished || executor_.isShutdown()) {
                  executor_.shutdown();
                  pullSocket_.close();
                  return;
               }
//            } catch (ExecutionException ex) {
//               JOptionPane.showMessageDialog(null, ex.getMessage());
            } catch (Exception e) {
               if (executor_.isShutdown()) {
                  return; //It was aborted
               }
               e.printStackTrace();
               acq_.abort(e);
               throw new RuntimeException(e);
            }

         }
      });
   }

   void setAcquisition(Acquisition aThis) {
      acq_ = aThis;
   }

   public int getPort() {
      return pullSocket_.getPort();
   }

   /**
    * Return true when all events finished and everything shutdown
    * @return
    */
   public boolean isFinished() {
      return executor_.isTerminated();
   }

   /**
    * This method needed so the source can be shutdown from x out on the viewer, 
    * rather than sending a finished event like normal
    */
   void abort() {
      executor_.shutdownNow();
      pullSocket_.close();
   }

}
