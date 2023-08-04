package org.micromanager.internal.zmq;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.concurrent.ConcurrentHashMap;

import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.zeromq.SocketType;
import org.zeromq.ZContext;
import org.zeromq.ZMQ;

// Base class that wraps a ZMQ socket and implements type conversions as well 
// as the impicit JSON message syntax
public abstract class ZMQSocketWrapper {

   protected static ZContext context_;

   //map of port numbers to servers, each of which has its own thread and base class
   protected static ConcurrentHashMap<Integer, ZMQSocketWrapper> portSocketMap_
           = new ConcurrentHashMap<Integer, ZMQSocketWrapper>();
   public static int STARTING_PORT_NUMBER = 4827;
//   public static int nextPort_ = DEFAULT_MASTER_PORT_NUMBER;

   protected SocketType type_;
   protected volatile ZMQ.Socket socket_;
   protected int port_;

   private boolean closed_ = false;

   public ZMQSocketWrapper(SocketType type, int port) {
      STARTING_PORT_NUMBER = port;
      type_ = type;
      if (context_ == null) {
         context_ = new ZContext();
      }
      port_ = nextPortNumber(this);
      initialize(port_);
   }

   public ZMQSocketWrapper(SocketType type) {
      this(type, STARTING_PORT_NUMBER);
   }

   private static synchronized int nextPortNumber(ZMQSocketWrapper t) {
      int port = STARTING_PORT_NUMBER;
      while (portSocketMap_.containsKey(port)) {
         port++;
      }
      portSocketMap_.put(port, t);
      return port;
   }
   
   public int getPort() {
      return port_;
   }

   public abstract void initialize(int port);
   
   public void close() {
      synchronized (socket_) {
         if (closed_) {
            return;
         }
         socket_.close();
         portSocketMap_.remove(this.getPort());
         closed_ = true;
      }
   }

   /**
    * Extract all byte arrays so their values can be sent seperately
    * @param binaryData
    * @param json
    * @throws JSONException
    */
   private void recurseBinaryData(ArrayList<byte[]> binaryData, Object json) throws JSONException {
      if (json instanceof JSONObject) {
         Iterator<String> keys = ((JSONObject) json).keys();
         while (keys.hasNext()) {
               String key = keys.next();
               Object value = ((JSONObject) json).get(key);
               if (value instanceof byte[]) {
                  binaryData.add((byte[]) value);
               } else if (value instanceof JSONObject ||  value instanceof JSONArray) {
                  recurseBinaryData(binaryData, value);
               }
            }
      } else if (json instanceof JSONArray) {
         for (int i = 0; i < ((JSONArray) json).length(); i++) {
            Object value = ((JSONArray) json).get(i);
            if (value instanceof byte[]) {
               binaryData.add((byte[]) value);
            } else if (value instanceof JSONObject ||  value instanceof JSONArray) {
               recurseBinaryData(binaryData, value);
            }
         }
      }
   }

   /**
    * Send a json object as a message, removing binary data as needed and sending in multiple parts
    * @param json
    */
   public void sendMessage(JSONObject json) {
      ArrayList<byte[]> byteData = new ArrayList<byte[]>();
      try {
         recurseBinaryData(byteData, json);
      } catch (JSONException e) {
         throw new RuntimeException(e);
      }

      if (byteData.size() == 0) {
         socket_.send(json.toString().getBytes( StandardCharsets.ISO_8859_1));
      } else {
         socket_.sendMore(json.toString().getBytes( StandardCharsets.ISO_8859_1));
         for (int i = 0; i < byteData.size() - 1; i ++) {
            socket_.sendMore(ByteBuffer.allocate(4).order(ByteOrder.nativeOrder()).putInt(
                    System.identityHashCode(byteData.get(i))).array());
            socket_.sendMore(byteData.get(i));
         }
         socket_.sendMore(ByteBuffer.allocate(4).order(ByteOrder.nativeOrder()).putInt(
                 System.identityHashCode(byteData.get(byteData.size() - 1))).array());
         socket_.send(byteData.get(byteData.size() - 1));
      }
   }

   /**
    * Recursively search through recieved message and replace byte buffer hashes with their values
    */
   private void insertByteBuffer(Object json, long hash, byte[] value) throws JSONException {
      if (json instanceof JSONObject) {
         Iterator<String> keys = ((JSONObject) json).keys();
         while (keys.hasNext()) {
            String key = keys.next();
            Object o = ((JSONObject) json).get(key);
            if (o instanceof String && ((String) o).contains("@")) {
               int intID = Integer.parseInt(((String) o).substring(1).split("_")[0]);
               int bytesPerEntry = Integer.parseInt(((String) o).substring(1).split("_")[1]);
               if (intID == hash) {
                  ((JSONObject) json).put(key, decodeByteArray(value, bytesPerEntry));
                  return;
               }
            } else if (o instanceof JSONObject) {
               insertByteBuffer(o, hash, value);
            } else if (o instanceof JSONArray) {
               insertByteBuffer(o, hash, value);
            }
         }
      } else if (json instanceof JSONArray) {
         for (int i = 0; i < ((JSONArray) json).length(); i++) {
            Object o = ((JSONArray) json).get(i);
            if (o instanceof String && ((String) o).contains("@")) {
               int intID = Integer.parseInt(((String) o).substring(1).split("_")[0]);
               int bytesPerEntry = Integer.parseInt(((String) o).substring(1).split("_")[1]);
               if (intID == hash) {
                  ((JSONArray) json).put(i, decodeByteArray(value, bytesPerEntry));
                  return;
               }
            } else if (o instanceof JSONObject) {
               insertByteBuffer(o, hash, value);
            } else if (o instanceof JSONArray) {
               insertByteBuffer(o, hash, value);
            }
         }
      }
   }

   //TODO: this is redundant to a function in ZMQUtil.
   // There are multiple mechanisms for byte data to be decoded. these should be consolidated
   // and consistent with the outgoing messages
   private Object decodeByteArray(byte[] value, int bytesPerEntry) {
      if (bytesPerEntry == 0) {
         return value; // it was sent over as raw binary. Might get converted at a high level
      } else if (bytesPerEntry == 1) {
         return value;
      } else if (bytesPerEntry == 2) {
         short[] shorts = new short[value.length / 2];
         ByteBuffer.wrap(value).order(ByteOrder.nativeOrder()).asShortBuffer().get(shorts);
         return shorts;
      } else if (bytesPerEntry == 4) {
         int[] ints = new int[value.length / 4];
         ByteBuffer.wrap(value).order(ByteOrder.nativeOrder()).asIntBuffer().get(ints);
         return ints;
      }
      throw new RuntimeException("unknown bytes per pixel");
   }

   public JSONObject receiveMessage() {
      ArrayList<byte[]> byteData = new ArrayList<byte[]>();
      String message = new String(socket_.recv(),  StandardCharsets.ISO_8859_1);
      JSONObject json;
      try {
         json = new JSONObject(message);
      } catch (JSONException e) {
         throw new RuntimeException(e);
      }
      while (socket_.hasReceiveMore()) {
         byteData.add(socket_.recv());
      }
      //Unpack byte data
      for (int i = 0; i < byteData.size(); i+=2) {
         ByteBuffer byteBuffer = ByteBuffer.wrap(byteData.get(i));
         int hash = byteBuffer.order(ByteOrder.nativeOrder()).asIntBuffer().get();
         byte[] value = byteData.get(i + 1);
         try {
            insertByteBuffer(json, hash, value);
         } catch (JSONException e) {
            throw new RuntimeException(e);
         }
      }
      return json;
   }

}
