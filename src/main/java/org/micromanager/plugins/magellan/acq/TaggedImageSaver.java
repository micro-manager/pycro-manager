///////////////////////////////////////////////////////////////////////////////
// AUTHOR:       Henry Pinkard, henry.pinkard@gmail.com
//
// COPYRIGHT:    University of California, San Francisco, 2015
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
package main.java.org.micromanager.plugins.magellan.acq;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import main.java.org.micromanager.plugins.magellan.misc.Log;
import main.java.org.micromanager.plugins.magellan.misc.MD;

/**
 * Dequeue tagged images and append to image cache
 *
 * copied from MM DefaultMagellanTaggedImageQueue
 */
public class TaggedImageSaver {
   
   private MMImageCache imageCache_ = null;
   private final Acquisition acq_;
   private final ExecutorService savingExecutor_;

   public TaggedImageSaver(MMImageCache imageCache, Acquisition acq) {
      imageCache_ = imageCache;
      acq_ = acq;
      savingExecutor_ = Executors.newSingleThreadExecutor(new ThreadFactory() {
         @Override
         public Thread newThread(Runnable r) {
            return new Thread(r, acq_.getName() + ": Saving thread");
         }
      });
   }

   public void waitForShutdown() {
      //wait for shutdown
      try {
         //wait for it to exit
         while (!savingExecutor_.awaitTermination(5, TimeUnit.MILLISECONDS)) {
         }
      } catch (InterruptedException ex) {
         Log.log("Unexpected interrupt while waiting for TaggedImageSaver to finish", true);
         //shouldn't happen
      }
   }

   public Future submit(final MagellanTaggedImage image) {              
      return savingExecutor_.submit(new Runnable() {
         @Override
         public void run() {            
            if (SignalTaggedImage.isAcquisitionFinsihedSignal(image)) {
               imageCache_.finished();
            } else {
                imageCache_.putImage(image);
            }
         }
      });
   }


}
