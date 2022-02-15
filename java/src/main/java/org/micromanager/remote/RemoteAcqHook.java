/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.remote;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.api.AcquisitionAPI;
import org.micromanager.acqj.main.AcquisitionEvent;
import org.micromanager.acqj.api.AcquisitionHook;
import org.micromanager.internal.zmq.ZMQPullSocket;
import org.micromanager.internal.zmq.ZMQPushSocket;

/**
 *
 * @author henrypinkard
 */
public class RemoteAcqHook implements AcquisitionHook {

   ZMQPushSocket<AcquisitionEvent> pushSocket_;
   ZMQPullSocket<List<AcquisitionEvent>> pullSocket_;

   public RemoteAcqHook(AcquisitionAPI acq) {
//      if (((RemoteAcquisition) acq).debugMode_) {
//         ((RemoteAcquisition) acq).core_.logMessage("Making push socket");
//      }
      pushSocket_ = new ZMQPushSocket<AcquisitionEvent>(
              new Function<AcquisitionEvent, JSONObject>() {
         @Override
         public JSONObject apply(AcquisitionEvent t) {
            return t.toJSON();
         }
      });

//      if (((RemoteAcquisition) acq).debugMode_) {
//         ((RemoteAcquisition) acq).core_.logMessage("Making pull socket");
//      }
      pullSocket_ = new ZMQPullSocket<List<AcquisitionEvent>>(
              new Function<JSONObject, List<AcquisitionEvent>>() {
                 @Override
                 public List<AcquisitionEvent> apply(JSONObject t) {
                    try {
                       List<AcquisitionEvent> eventList = new ArrayList<AcquisitionEvent>();
                       if (t.has("events")) { // list of events
                          JSONArray events = t.getJSONArray("events");
                          for (int i = 0; i < events.length(); i++) {
                             JSONObject e = events.getJSONObject(i);
                             eventList.add(AcquisitionEvent.fromJSON(e, acq));
                          }
                       } else { //single event
                          eventList.add(AcquisitionEvent.fromJSON(t, acq));
                       }

                       return eventList;
                    } catch (JSONException ex) {
                       throw new RuntimeException("Incorrect format for acquisitio event");
                    }
                 }
              });
//      if (((RemoteAcquisition) acq).debugMode_) {
//         ((RemoteAcquisition) acq).core_.logMessage("made pull socket");
//      }
   }

   @Override
   public AcquisitionEvent run(AcquisitionEvent event) {
      pushSocket_.push(event);
      List<AcquisitionEvent> ae = pullSocket_.next();
      if (ae.size() == 1) {
         return ae.get(0);
      } else {
         return new AcquisitionEvent(ae);
      }
   }

   public int getPullPort() {
      return pullSocket_.getPort();
   }

   public int getPushPort() {
      return pushSocket_.getPort();
   }

   @Override
   public void close() {
      pushSocket_.close();
      pullSocket_.close();
   }

}
