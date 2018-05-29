/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package main.java.org.micromanager.plugins.magellan.autofocus;

import java.io.File;
import java.io.IOException;
import java.nio.IntBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Random;
import org.tensorflow.SavedModelBundle;
import org.tensorflow.Session;
import org.tensorflow.Tensor;

/**
 *
 * @author Henry
 */
public class SingleShotAutofocus {

    private static SingleShotAutofocus singleton_;

    public SingleShotAutofocus() {
        singleton_ = this;
    }

    public double predictDefocus(short[] image) {

        return 0.0;
    }

    public static SingleShotAutofocus getInstance() {
        return singleton_;
    }

    public void loadModel(File f) {
        //either load model or throw exception



//            Graph g = new Graph();
//            final String value = "Hello from " + TensorFlow.version();
//
//            // Construct the computation graph with a single operation, a constant
//            // named "MyConst" with a value "value".
//            Tensor t = Tensor.create(value.getBytes("UTF-8"));
//            // The Java API doesn't yet include convenience functions for adding operations.
//            g.opBuilder("Const", "MyConst").setAttr("dtype", t.dataType()).setAttr("value", t).build();
//
//            // Execute the "MyConst" operation in a Session.
//            Session s = new Session(g);
//            Tensor output = s.runner().fetch("MyConst").run().get(0);
//            System.out.println(new String(output.bytesValue(), "UTF-8"));

      

        //store preferred model path so it can be reloaded on startup
    }

    public String getModelName() {
        return "TODO";
    }

    public static void main(String[] args) {

      SavedModelBundle b = SavedModelBundle.load("/Users/henrypinkard/Google Drive/Code/GitRepos/Leukosight/analysis/autofocus/exported_model/","serve");
       
      Session s = b.session();
       
        int[] data = new int[1028*1028]; 
        Random random = new Random();
        
        for (int i = 0; i < data.length; i++) {
           data[i] = random.nextInt(4096);
        }
        
        long[] shape = new long[]{1,1028,1028};
        Tensor input = Tensor.create(shape, IntBuffer.wrap(data));
         
       s.runner().feed("predict_input/input", input).fetch("predict_network/output").run().get(0).expect(Float.class);

       long start = System.currentTimeMillis();
       Tensor<Float> result = s.runner().feed("predict_input/input", input).fetch("predict_network/output").run().get(0).expect(Float.class);
       System.out.println("Time to evaluate:" + (System.currentTimeMillis() - start) );
       
       float[] res=new float[1];
       result.copyTo(res); 
       double predictedDefocus = res[0];
      // Generally, there may be multiple output tensors, all of them must be closed to prevent resource leaks.
       
//       float[][] res = new float[1][1];
//       res[0] = new float[1];
//       result.copyTo(res);
       System.out.println("results: " + predictedDefocus);
//
//
//        // Generally, there may be multiple output tensors, all of them must be closed to prevent resource leaks.
//        Tensor<Float> predictedDefocusTensor = s.runner().feed("input", input).fetch("output").run().get(0).expect(Float.class);
//
//        double predictedDefocus = predictedDefocusTensor.doubleValue();
        

        //TODO: close all resources
    }


    private static byte[] readAllBytesOrExit(Path path) {
        try {
            return Files.readAllBytes(path);
        } catch (IOException e) {
            System.err.println("Failed to read [" + path + "]: " + e.getMessage());
            System.exit(1);
        }
        return null;
    }

}
