package org.micromanager.lightsheet;


import mmcorej.TaggedImage;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;
import org.micromanager.acqj.main.AcqEngMetadata;

import java.util.ArrayList;
import java.util.Collections;
import java.util.concurrent.LinkedBlockingDeque;

public class LightSheetStackTests {

   private static int getImageWidth(ImagePlus imagePlus) {
      ImageStack stack = imagePlus.getStack();
      ImageProcessor ip = stack.getProcessor(1);
      return ip.getWidth();
   }

   private static int getImageHeight(ImagePlus imagePlus) {
      ImageStack stack = imagePlus.getStack();
      ImageProcessor ip = stack.getProcessor(1);
      return ip.getHeight();
   }

   private static ArrayList<short[]> loadTiffStack(ImagePlus imagePlus) {
      ArrayList<short[]> images = new ArrayList<>();

      ImageStack stack = imagePlus.getStack();
      int numSlices = stack.getSize();

      for (int i = 1; i <= numSlices; i++) {
         ImageProcessor ip = stack.getProcessor(i);
         short[] pixels = (short[]) ip.getPixels();
         images.add(pixels);
      }

      Collections.reverse(images);
      return images;
   }

   private static ArrayList<TaggedImage> convertToTaggedImages(ArrayList<short[]> stack,
                                                        int imageWidth, int imageHeight) {
      // convert imageJ to tagged image
      ArrayList<TaggedImage> taggedImages = new ArrayList<>();
      for (int i = 0; i < stack.size(); i++) {
         short[] image = stack.get(i);
         JSONObject tags = new JSONObject();
         try {
            tags.put("Width", imageWidth);
            tags.put("Height", imageHeight);
            JSONObject axes = new JSONObject();
            axes.put(AcqEngMetadata.Z_AXIS, i);
            tags.put("Axes", axes);
         } catch (JSONException e) {
            e.printStackTrace();
         }
         taggedImages.add(new TaggedImage(image, tags));
      }
      return taggedImages;
   }

   private static Object[] resampleVolumeWithAcqEngJInterface(ArrayList<short[]> stack, int imageWidth, int imageHeight,
                                                              double theta, double pixelSizeXYUm, double zStepUm,
                                                              int numToTime) {

      ArrayList<TaggedImage> taggedImages = convertToTaggedImages(stack, imageWidth, imageHeight);
      // Simulate several z stacks in sequence
      StackResamplersImageProcessor processor = new StackResamplersImageProcessor(
              StackResampler.FULL_VOLUME, theta, pixelSizeXYUm,
              zStepUm, stack.size(), imageWidth, imageHeight, 1,
              false, true, true);
      processor.setAcqAndDequeues(null, new LinkedBlockingDeque<>(), new LinkedBlockingDeque<>());


      for (int i = 0; i < numToTime; i++) {
         processor.getOutputQueue().clear();
         long startTime = System.currentTimeMillis();
         for (TaggedImage taggedImage : taggedImages) {
            processor.processImage(taggedImage);
         }
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");
      }
      ArrayList<short[]> resampledVolume = new ArrayList<>();
      while (!processor.getOutputQueue().isEmpty()) {
         resampledVolume.add((short[]) processor.getOutputQueue().removeFirst().pix);
      }
      return new Object[]{resampledVolume, processor.getResampledShapeZ(),
              processor.getResampledShapeY(), processor.getResampledShapeX()};
   }

   private static Object[] fusedOrthognalWithAcqEngJInterface(ArrayList<short[]> stack, int imageWidth, int imageHeight,
                                                             double theta, double pixelSizeXYUm, double zStepUm,
                                                            int numToTime) {

      ArrayList<TaggedImage> taggedImages = convertToTaggedImages(stack, imageWidth, imageHeight);
      // Simulate several z stacks in sequence
      StackResamplersImageProcessor processor = new StackResamplersImageProcessor(
              StackResampler.OTHOGONAL_VIEWS, theta, pixelSizeXYUm,
              zStepUm, stack.size(), imageWidth, imageHeight, 1,
              false, true, true);
      processor.setAcqAndDequeues(null, new LinkedBlockingDeque<>(), new LinkedBlockingDeque<>());


      for (int i = 0; i < numToTime; i++) {
         processor.getOutputQueue().clear();
         long startTime = System.currentTimeMillis();
         for (TaggedImage taggedImage : taggedImages) {
            processor.processImage(taggedImage);
         }
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");
      }
      short[] fusedOrthogonalViews = (short[]) processor.getOutputQueue().getLast().pix;
      int fusedImageWidth = processor.getResampledShapeX() + processor.getResampledShapeZ();
      int fusedImageHeight = processor.getResampledShapeY() + processor.getResampledShapeZ();

      return new Object[]{fusedOrthogonalViews, fusedImageHeight, fusedImageWidth};
   }

   private static Object[] yxProjWithAcqEngJInterface(ArrayList<short[]> stack, int imageWidth, int imageHeight,
                                                             double theta, double pixelSizeXYUm, double zStepUm,
                                                              int numToTime) {

      ArrayList<TaggedImage> taggedImages = convertToTaggedImages(stack, imageWidth, imageHeight);
      // Simulate several z stacks in sequence
      StackResamplersImageProcessor processor = new StackResamplersImageProcessor(
              StackResampler.YX_PROJECTION, theta, pixelSizeXYUm, zStepUm,
              stack.size(), imageWidth, imageHeight, 1,
              false, true, true);
      processor.setAcqAndDequeues(null, new LinkedBlockingDeque<>(), new LinkedBlockingDeque<>());


      for (int i = 0; i < numToTime; i++) {
         processor.getOutputQueue().clear();
         long startTime = System.currentTimeMillis();
         for (TaggedImage taggedImage : taggedImages) {
            processor.processImage(taggedImage);
         }
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");
      }
      short[] yxProj = (short[]) processor.getOutputQueue().getLast().pix;
      return new Object[]{yxProj,  processor.getResampledShapeY(), processor.getResampledShapeX()};
   }


   private static Object[] orthoViewsSeperateWithAcqEngJInterface(ArrayList<short[]> stack, int imageWidth, int imageHeight,
                                                      double theta, double pixelSizeXYUm, double zStepUm,
                                                      int numToTime) {

      ArrayList<TaggedImage> taggedImages = convertToTaggedImages(stack, imageWidth, imageHeight);
      // Simulate several z stacks in sequence
      StackResamplersImageProcessor processor = new StackResamplersImageProcessor(
              StackResampler.OTHOGONAL_VIEWS, theta, pixelSizeXYUm, zStepUm,
              stack.size(), imageWidth, imageHeight, 1,
              false, false, true);
      processor.setAcqAndDequeues(null, new LinkedBlockingDeque<>(), new LinkedBlockingDeque<>());


      for (int i = 0; i < numToTime; i++) {
         processor.getOutputQueue().clear();
         long startTime = System.currentTimeMillis();
         for (TaggedImage taggedImage : taggedImages) {
            processor.processImage(taggedImage);
         }
         long endTime = System.currentTimeMillis();
         System.out.println("Processing time: " + (endTime - startTime) + " ms");
      }
      short[] yxProj = (short[]) processor.getOutputQueue().removeFirst().pix;
      short[] zyProj = (short[]) processor.getOutputQueue().removeFirst().pix;
      short[] zxProj = (short[]) processor.getOutputQueue().removeFirst().pix;
      return new Object[]{yxProj, zyProj, zxProj,
              processor.getResampledShapeZ(), processor.getResampledShapeY(), processor.getResampledShapeX()};
   }


   private static void displayResampledVolume(Object[] o) {
      ArrayList<short[]> resampledVolume = (ArrayList<short[]>) o[0];
      int sizeZ = (int) o[1];
      int sizeY = (int) o[2];
      int sizeX = (int) o[3];

      new ImageJ();
      ImageStack imageStack = new ImageStack(sizeX, sizeY);
      for (short[] img : resampledVolume) {
         imageStack.addSlice("z", img);
      }
      ImagePlus projectionImage = new ImagePlus("volume", imageStack);
      projectionImage.show();
   }

   private static void displayYXProjection(Object[] o) {
      short[] img = (short[]) o[0];
      int height = (int) o[1];
      int width = (int) o[2];

      new ImageJ();
      ImageStack imageStack = new ImageStack(width, height);
      imageStack.addSlice("yx", img);
      ImagePlus projectionImage = new ImagePlus("yx", imageStack);
      projectionImage.show();
   }

   private static void displayFusedOrthoViews(Object[] o) {
      short[] img = (short[]) o[0];
      int height = (int) o[1];
      int width = (int) o[2];

      //display in imageJ
      new ImageJ();
      ImageStack imageStack = new ImageStack(width, height);
      imageStack.addSlice("ortho", img);
      ImagePlus projectionImage = new ImagePlus("ortho", imageStack);
      projectionImage.show();

   }
   public static void displaySeperateOrthoViews(Object[] o) {
      short[] yx = (short[]) o[0];
      short[] zy = (short[]) o[1];
      short[] zx = (short[]) o[2];
      int imageShapeX = (int) o[5];
      int imageShapeY = (int) o[4];
      int imageShapeZ = (int) o[3];


      //display in imageJ
      //open the imagej toolbar
      new ImageJ();

      ImageStack imageStack = new ImageStack(imageShapeX, imageShapeY);
      imageStack.addSlice("yx", yx);
      ImagePlus projectionImage = new ImagePlus("yx", imageStack);
      projectionImage.show();

      imageStack = new ImageStack(imageShapeY, imageShapeZ);
      imageStack.addSlice("zy", zy);
      projectionImage = new ImagePlus("zy", imageStack);
      projectionImage.show();

      imageStack = new ImageStack(imageShapeX, imageShapeZ);
      imageStack.addSlice("zx", zx);
      projectionImage = new ImagePlus("zx", imageStack);
      projectionImage.show();
   }


//   import ij.ImageJ;
//   import ij.ImagePlus;
//   import ij.ImageStack;
//   import ij.process.ImageProcessor;
//   public static void main(String[] args) {
//      String tiffPath = "/Users/henrypinkard/Desktop/rings_test.tif";
//      double zStepUm = 0.13;
//      double pixelSizeXYUm = 0.116;
//      double theta = 0.46;
//
//      ImagePlus imagePlus = new ImagePlus(tiffPath);
//      int shapeX = getImageWidth(imagePlus);
//      int shapeY = getImageHeight(imagePlus);
//      int shapeZ = imagePlus.getStack().getSize();
//      ArrayList<short[]> stack = loadTiffStack(imagePlus);
//
//      // downsample the stack taking every other
////      int downsamplingFactorZ = 2;
////      ArrayList<short[]> downsampledStack = new ArrayList<>();
////        for (int i = 0; i < stack.size(); i++) {
////             if (i % downsamplingFactorZ == 0) {
////                downsampledStack.add(stack.get(i));
////             }
////        }
////        stack = downsampledStack;
////        zStepUm *= downsamplingFactorZ;
//
//
//      // keep only first 256 elements
////        stack = new ArrayList<short[]>(stack.subList(0, 256));
//
////         create a new stack of images with teh y axis downsized by a factor of
////      int downsamplingFactor = 4;
////        for (int i = 0; i < stack.size(); i++) {
////             short[] image = stack.get(i);
////             short[] newImage = new short[image.length / downsamplingFactor];
////             for (int j = 0; j < newImage.length; j++) {
////                 newImage[j] = image[j * downsamplingFactor];
////             }
////             stack.set(i, newImage);
////         }
////         imageWidth /= downsamplingFactor;
//
//      System.out.println("Stack size: " + stack.size());
//      System.out.println("Image width: " + shapeX + " Image height: " + shapeY);
//
//      Object[] ret;
//
////      displayResampledVolume(resampleVolumeWithAcqEngJInterface(stack, shapeX, shapeY, theta,
////              pixelSizeXYUm, zStepUm, 100));
//
////      displayYXProjection(yxProjWithAcqEngJInterface(stack, shapeX, shapeY, theta,
////              pixelSizeXYUm, zStepUm, 200));
//
//      displayFusedOrthoViews(fusedOrthognalWithAcqEngJInterface(stack, shapeX, shapeY, theta,
//              pixelSizeXYUm, zStepUm, 100));
//
////      displaySeperateOrthoViews(orthoViewsSeperateWithAcqEngJInterface(stack, shapeX, shapeY, theta,
////              pixelSizeXYUm, zStepUm, 1));
//
//   }



}
