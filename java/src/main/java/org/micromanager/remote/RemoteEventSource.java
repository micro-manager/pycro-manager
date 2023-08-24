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
      //constantly poll the socket for more event sequences to submit
      executor_.submit(() -> {
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
         try {
            System.out.println("pull socket started");
            while (true) {
               List<AcquisitionEvent> eList = pullSocket_.next();
               boolean finished = eList.get(eList.size() - 1).isAcquisitionFinishedEvent();
               Future result = acq_.submitEventIterator(eList.iterator());
               result.get(); //propogate any exceptions
               if (finished || executor_.isShutdown()) {
                  executor_.shutdown();
                  break;
               }
            }
         } catch (InterruptedException e) {
            // it was aborted
         } catch (Exception e) {
            e.printStackTrace();
            if (!executor_.isShutdown()) {
               acq_.abort(e);
            }
         } finally {
            pullSocket_.close();
         }

      });
   }

   void setAcquisition(Acquisition aThis) {
      acq_ = aThis;
   }

   public int getPort() {
      while (pullSocket_ == null) {
         // wait for it to be created ona different thread
         try {
            Thread.sleep(1);
         } catch (InterruptedException e) {
            e.printStackTrace();
         }
      }
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
    *
    * It causes the pull socket to shutdown without getting a signal from the push
    * socket sending in events. Thus it is up to the code on that side to ensure it is properly
    * shut down
    */
   void abort() {
      executor_.shutdown();
      while(!executor_.isTerminated()) {
         try {
            Thread.sleep(1);
         } catch (InterruptedException e) {
            e.printStackTrace();
         }
      };

   }

}
