package org.micromanager.remote;

import mmcorej.CMMCore;
import org.micromanager.acqj.internal.acqengj.Engine;
import org.micromanager.internal.zmq.ZMQServer;

import java.io.UnsupportedEncodingException;
import java.net.URISyntaxException;
import java.util.HashSet;
import java.util.function.Consumer;
import java.util.function.Function;

public class HeadlessLauncher {

   private static Engine engine_;
   private static ZMQServer zmqServer_;

   public static void main(String[] args) throws Exception {

      CMMCore core = new CMMCore();

      //Start acq Engine
      engine_ = new Engine(core);

      //Start ZMQ server
      Function<Class, Object> instanceGrabberFunction = new Function<Class, Object>() {
         @Override
         public Object apply(Class baseClass) {
            //return instances of existing objects
            if (baseClass.equals(CMMCore.class)) {
               return core;
            }
            return null;
         }
      };


      try {
         HashSet<ClassLoader> classLoaders = new HashSet<ClassLoader>();
         classLoaders.add(core.getClass().getClassLoader());
         zmqServer_ = new ZMQServer(classLoaders, instanceGrabberFunction, new String[]{},
                 new Consumer<String>() {
                    @Override
                    public void accept(String s) {
                       System.out.println(s);
                    }
                 });
      } catch (URISyntaxException e) {
         throw new RuntimeException();
      } catch (UnsupportedEncodingException e) {
         throw new RuntimeException();
      }
   }

}
