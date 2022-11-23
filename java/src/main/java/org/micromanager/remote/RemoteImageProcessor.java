/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.function.Function;
import mmcorej.TaggedImage;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.acqj.main.AcqEngMetadata;
import org.micromanager.acqj.api.TaggedImageProcessor;
import org.micromanager.acqj.main.Acquisition;
import org.micromanager.internal.zmq.ZMQPullSocket;
import org.micromanager.internal.zmq.ZMQPushSocket;
import org.micromanager.internal.zmq.ZMQUtil;

// TODO: this class now duplicates functionality of AsyncImageProcessor in AcqEngJ

/**
 * Implements an ImageProcessor that sends/recieves images from a remote source
 * using ZMQ push/pull sockets. This enables image processing in Python/NumPy
 *
 * @author henrypinkard
 */
public class RemoteImageProcessor implements TaggedImageProcessor {

   private ExecutorService pushExecutor_, pullExecutor_;

   volatile LinkedBlockingDeque<TaggedImage> source_, sink_;

   ZMQPushSocket<TaggedImage> pushSocket_;
   ZMQPullSocket<TaggedImage> pullSocket_;

   public RemoteImageProcessor() {
      pushSocket_ = new ZMQPushSocket<TaggedImage>(
              new Function<TaggedImage, JSONObject>() {
         @Override
         public JSONObject apply(TaggedImage t) {
            try {
               JSONObject json = new JSONObject();
               if (t.tags == null && t.pix == null) {
                  json.put("special", "finished");
               } else {
                  json.put("metadata", t.tags);
                  json.put("pixels", ZMQUtil.toJSON(t.pix));
               }
               return json;
            } catch (JSONException ex) {
               throw new RuntimeException(ex);
            }
         }
      });

      pullSocket_ = new ZMQPullSocket<TaggedImage>(
              new Function<JSONObject, TaggedImage>() {
         @Override
         public TaggedImage apply(JSONObject t) {
            try {
               if (t instanceof JSONObject && ((JSONObject) t).has("special")
                       && ((JSONObject) t).getString("special").equals("finished")) {
                  return new TaggedImage(null, null);
               } else {
                  JSONObject tags = ((JSONObject) t).getJSONObject("metadata");
                  Object pix = ZMQUtil.decodeArray((byte[]) ((JSONObject) t).get("pixels"),
                          (AcqEngMetadata.getBytesPerPixel(tags) == 1 ||
                                  AcqEngMetadata.getBytesPerPixel(tags) == 4) ? byte[].class : short[].class);
                  return new TaggedImage(pix, tags);
               }
            } catch (JSONException ex) {
               throw new RuntimeException(ex);
            }
         }
      });
      pushExecutor_ = Executors.newSingleThreadExecutor(
              (Runnable r) -> new Thread(r, "Tagged Image socket push"));
      pullExecutor_ = Executors.newSingleThreadExecutor(
              (Runnable r) -> new Thread(r, "Tagged Image socket pull"));
   }

   public int getPullPort() {
      return pullSocket_.getPort();
   }

   public int getPushPort() {
      return pushSocket_.getPort();
   }

   public void startPush() {
      // Pushing will get shut down when a null/null image comes through signalling
      // the acquisition is finished
      pushExecutor_.submit(() -> {
         //take from source and push as fast as possible
         while (true) {
            if (source_ != null) {
               try {
                  TaggedImage img = source_.takeFirst();
                  pushSocket_.push(img);
                  if (img.tags == null && img.pix == null) {
                     // all images have been pushed
                     pushExecutor_.shutdown();
                     break;
                  }
               } catch (InterruptedException ex) {
                  return;
               } catch (Exception e) {
                  e.printStackTrace();
                  break;
               }
            }
         }
         pushSocket_.close();
      });
   }

   // Pulling will get shutdown based on a signal from python side indicating that
   // it will not push anything more
   public void startPull() {
      pullExecutor_.submit(() -> {
         while (true) {
            if (sink_ != null) {
               try {
                  TaggedImage ti = pullSocket_.next();
                  sink_.putLast(ti);
                  if (ti.pix == null && ti.tags == null) {
                     pullExecutor_.shutdown();
                     break;
                  }
               } catch (InterruptedException ex) {
                  return;
               } catch (Exception e) {
                  if (pullExecutor_.isShutdown()) {
                     return;
                  }
                  e.printStackTrace();
               }
            }
         }
         pullSocket_.close();
      });
   }

   @Override
   public void setAcqAndDequeues(AcquisitionAPI acq,
                           LinkedBlockingDeque<TaggedImage> source, LinkedBlockingDeque<TaggedImage> sink) {
      source_ = source;
      sink_ = sink;
   }


}
