/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import java.nio.ByteBuffer;
import java.util.concurrent.*;

import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.internal.zmq.ZMQPushSocket;
import org.micromanager.ndtiffstorage.ImageWrittenListener;
import org.micromanager.ndtiffstorage.IndexEntryData;
import org.micromanager.ndtiffstorage.NDTiffStorage;

/**
 * A class that broadcasts information about images that have finsihed saving to disk
 * @author henrypinkard
 */
public class RemoteStorageMonitor implements ImageWrittenListener {

   private ZMQPushSocket<IndexEntryData> pushSocket_;
   private ExecutorService executor_ = Executors.newSingleThreadExecutor((Runnable r) -> {
      return new Thread(r, "Remote storage monitor thread");
   });
   private LinkedBlockingDeque<IndexEntryData> indexEntries_ = new LinkedBlockingDeque<IndexEntryData>();

   public RemoteStorageMonitor() {
      executor_.submit(new Runnable() {
         @Override
         public void run() {
            pushSocket_ = new ZMQPushSocket<IndexEntryData>(
                    t -> {
                       try {
                          JSONObject message = new JSONObject();
                          if (t.isDataSetFinishedEntry()) {
                             message.put("finished", true);
                          } else {
                             message.put("index_entry", ((ByteBuffer) t.asByteBuffer()).array());
                          }
                          return message;
                       } catch (JSONException e) {
                          throw new RuntimeException("Problem with data saved socket");
                       }
                    });
         }
      });
   }

   /**
    * Start pushing out the indices to the other side
    */
   public void start() {
      System.out.println("Starting remote storage monitor on port " + pushSocket_.getPort());
      //constantly poll the socket for more event sequences to submit
      executor_.submit(() -> {
         while (true) {
            IndexEntryData e = null;
            try {
               e = indexEntries_.takeFirst();
            } catch (InterruptedException ex) {
               // this should never happen
               ex.printStackTrace();
               throw new RuntimeException(ex);
            }

            if (e.dataSetFinishedEntry_) {
               pushSocket_.push(IndexEntryData.createFinishedEntry());
               // Ready for close, but need a signal that all messages have been received by java side
               return;
            } else {
               pushSocket_.push(e);
            }
         }
      });
   }


   public int getPort() {
      while (pushSocket_ == null) {
         try {
            Thread.sleep(1);
         } catch (InterruptedException e) {
            e.printStackTrace();
         }
      }
      return pushSocket_.getPort();
   }

   @Override
   /**
    * Called the storage to signal that a new image has finished writing
    */
   public void imageWritten(IndexEntryData ied) {
      indexEntries_.addLast(ied);
   }

   @Override
   public void awaitCompletion() {
      //deprecated
   }

   /**
    * Called by the python side to signal that the final shutdown signal has been received
    * and that the push socket can be closed
    */
   public void storageMonitoringComplete() {
      executor_.submit(() -> {
         pushSocket_.close();
         executor_.shutdown();
      });
   }

}
