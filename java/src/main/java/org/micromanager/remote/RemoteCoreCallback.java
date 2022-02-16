package org.micromanager.remote;///////////////////////////////////////////////////////////////////////////////
//PROJECT:       Micro-Manager
//SUBSYSTEM:     mmstudio
//-----------------------------------------------------------------------------
//
// AUTHOR:       
//
// COPYRIGHT:    University of California, San Francisco, 2014
//
// LICENSE:      This file is distributed under the BSD license.
//               License text is included with the source distribution.
//
//               This file is distributed in the hope that it will be useful,
//               but WITHOUT ANY WARRANTY; without even the implied warranty
//               of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//
//               IN NO EVENT SHALL THE COPYRIGHT OWNER OR
//               CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
//               INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES.
//

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.function.Function;
import mmcorej.CMMCore;
import mmcorej.MMEventCallback;
import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.internal.zmq.ZMQPushSocket;

/**
 * Class that connects core callbacks to a ZMQPush socket so they can be dispatched to external clients
 */
public final class RemoteCoreCallback extends MMEventCallback {

   private ExecutorService pushExecutor_;
   private ZMQPushSocket<JSONObject> pushSocket_;
   volatile LinkedBlockingDeque<JSONObject> eventList_ = new LinkedBlockingDeque<JSONObject>();

   private final CMMCore core_;


   public RemoteCoreCallback(CMMCore core) {
      super();
      core_ = core;
      core_.registerCallback(this);


      pushSocket_ = new ZMQPushSocket<JSONObject>(
              new Function<JSONObject, JSONObject>() {
                 @Override
                 public JSONObject apply(JSONObject t) {
                       return t;
                 }
              });

      pushExecutor_ = Executors.newSingleThreadExecutor(
              (Runnable r) -> new Thread(r, "Core callback thread"));
   }

   public int getPushPort() {
      return pushSocket_.getPort();
   }

   public void shutdown() {
      pushExecutor_.shutdownNow();
      pushSocket_.close();
   }

   public void startPush() {
      pushExecutor_.submit(() -> {
         //take from source and push as fast as possible
         while (true) {
               try {
                  JSONObject message = eventList_.takeFirst();
                  pushSocket_.push(message);
               } catch (InterruptedException ex) {
                  return;
               } catch (Exception e) {
                  if (pushExecutor_.isShutdown()) {
                     return;
                  }
                  e.printStackTrace();
               }
            }

      });
   }

   @Override
   public void onPropertiesChanged() {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "propertiesChanged");
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onPropertyChanged(String deviceName, String propName, String propValue) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "propertyChanged");
         JSONArray args = new JSONArray();
         args.put(deviceName);
         args.put(propName);
         args.put(propValue);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onChannelGroupChanged(String newChannelGroupName) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "channelGroupChanged");
         JSONArray args = new JSONArray();
         args.put(newChannelGroupName);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onConfigGroupChanged(String groupName, String newConfig) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "configGroupChanged");
         JSONArray args = new JSONArray();
         args.put(groupName);
         args.put(newConfig);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onSystemConfigurationLoaded() {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "systemConfigurationLoaded");
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onPixelSizeChanged(double newPixelSizeUm) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "pixelSizeChanged");
         JSONArray args = new JSONArray();
         args.put(newPixelSizeUm);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onPixelSizeAffineChanged(double npa0, double npa1, double npa2,
                                        double npa3, double npa4, double npa5) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "pixelSizeAffineChanged");
         JSONArray args = new JSONArray();
         args.put(npa0);
         args.put(npa1);
         args.put(npa2);
         args.put(npa3);
         args.put(npa4);
         args.put(npa5);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onStagePositionChanged(String deviceName, double pos) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "stagePositionChanged");
         JSONArray args = new JSONArray();
         args.put(deviceName);
         args.put(pos);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onXYStagePositionChanged(String deviceName, double xPos, double yPos) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "XYStagePositionChanged");
         JSONArray args = new JSONArray();
         args.put(deviceName);
         args.put(xPos);
         args.put(yPos);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onExposureChanged(String deviceName, double exposure) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "exposureChanged");
         JSONArray args = new JSONArray();
         args.put(deviceName);
         args.put(exposure);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

   @Override
   public void onSLMExposureChanged(String deviceName, double exposure) {
      try {
         JSONObject message = new JSONObject();
         message.put("name", "SLMExposureChanged");
         JSONArray args = new JSONArray();
         args.put(deviceName);
         args.put(exposure);
         message.put("arguments", args);
         eventList_.addLast(message);
      } catch (JSONException e) {
         e.printStackTrace();
         core_.logMessage(e.toString());
      }
   }

}