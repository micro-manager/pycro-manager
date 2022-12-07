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
   private RemoteAcquisition acq_;
   private ExecutorService executor_ = Executors.newSingleThreadExecutor((Runnable r) -> {
      return new Thread(r, "Remote Event Source thread");
   });
   private LinkedBlockingDeque<IndexEntryData> indexEntries_ = new LinkedBlockingDeque<IndexEntryData>();
   private final String diskLocation_;
   private final JSONObject summaryMetadata_;

   public RemoteStorageMonitor(NDTiffStorage storage) {
      diskLocation_ = storage.getDiskLocation();
      summaryMetadata_ = storage.getSummaryMetadata();
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

   public JSONObject getSummaryMetadata() {
      return summaryMetadata_;
   }

   public String getDiskLocation() {
      return diskLocation_;
   }

   /**
    * Start pushing out the indices to the other side
    */
   public void start() {
      //constantly poll the socket for more event sequences to submit
      executor_.submit(() -> {
         while (true) {
            try {

               boolean finished = false;
               if (indexEntries_.size() > 0) {
                  IndexEntryData e = indexEntries_.takeFirst();
                  if (e.dataSetFinishedEntry_) {
                     finished = true;
                  } else {
                     pushSocket_.push(e);
                  }
               } else if (executor_.isShutdown()) {
                  finished = true;
               } else {
                  Thread.sleep(1);
               }


               if (finished ) {
                  pushSocket_.push(IndexEntryData.createFinishedEntry());
                  executor_.shutdown();
                  pushSocket_.close();
                  return;
               }
            }  catch (Exception e) {
               if (executor_.isShutdown()) {
                  return; //It was aborted
               }
               e.printStackTrace();
               throw new RuntimeException(e);
            }

         }
      });
   }


   public int getPort() {
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
      while (!executor_.isTerminated()) {
         try {
            Thread.sleep(5);
         } catch (InterruptedException e) {
            throw new RuntimeException(e);
         }
      }
   }
}
