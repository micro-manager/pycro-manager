/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package main.java.org.micromanager.plugins.magellan.acq;

import java.util.Iterator;
import java.util.Spliterator;
import java.util.Spliterators;
import java.util.function.IntUnaryOperator;
import java.util.stream.IntStream;
import java.util.stream.Stream;
import java.util.stream.StreamSupport;

/**
 *
 * @author henrypinkard
 */
public class tester {

   public static int numFrames_ = 40;
   
   public static void main(String[] args) {

//      Iterator<Integer> frameIndexIterator = new Iterator() {
//         int frameIndex_ = 0;
//
//         @Override
//         public boolean hasNext() {
//            if (frameIndex_ == 20) {
//               numFrames_ = 100;
//            }
//            if (frameIndex_ == 0) {
//               return true;
//            }
//            if ( frameIndex_ < numFrames_) {
//               return true;
//            }
//            return false;
//         }
//
//         @Override
//         public Object next() {
//            frameIndex_++;
//            return frameIndex_ - 1;
//         }
//      };
//      Stream<Integer> iStream = StreamSupport.stream(Spliterators.spliteratorUnknownSize(frameIndexIterator, Spliterator.DISTINCT), false);
//      iStream.forEach(s->System.out.println(s));
//      
      IntStream rangeStream = IntStream.range(0, numFrames_);
      rangeStream.limit(10).forEach(System.out::println);
      rangeStream.limit(10).forEach(System.out::println);      
   }

}
