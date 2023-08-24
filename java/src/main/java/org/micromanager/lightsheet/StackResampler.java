package org.micromanager.lightsheet;

import java.awt.Point;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Spliterator;
import java.util.Spliterators;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.StreamSupport;
import mmcorej.TaggedImage;
import org.micromanager.acqj.main.AcqEngMetadata;

/**
 * This class takes a ZYX stack of pixels and resamples it into a new coordinate space.
 * It is CPU parallelized for speed, and individual Z slices can be added as they become available
 * in order to speed processing. It can output either a full volume, a YX projection, or a set of
 * orthogonal views. All interpolation is done using nearest neighbors, and thus is very fast, but
 * should probably not be relied upon for quantitative analysis.
 */
public class StackResampler {

   public static final int YX_PROJECTION = 0;
   public static final int ORTHOGONAL_VIEWS = 1;
   public static final int FULL_VOLUME = 2;
   private final int mode_;


   private final double reconstructionVoxelSizeUm_;
   private final double[][] transformationMatrix_;
   private double[] reconCoordOffset_;
   private final int[] cameraImageShape_;
   private int[] reconImageShape_;

   private int[][] denominatorYXProjection_;
   private int[][] denominatorZXProjection_;
   private int[][] denominatorYZProjection_;
   private short[] meanProjectionYX_;
   private short[] meanProjectionZX_;
   private short[] meanProjectionYZ_;
   private final Object[][] lineLocks_;
   int[][] sumProjectionYX_ = null;
   int[][] sumProjectionYZ_ = null;
   int[][] sumProjectionZX_ = null;
   short[] maxProjectionYX_ = null;
   short[] maxProjectionYZ_ = null;
   short[] maxProjectionZX_ = null;
   short[][] reconVolumeZYX_ = null;
   private final BlockingQueue<ImagePlusSlice> imageQueue_ = new LinkedBlockingDeque<>();
   private HashMap<Point, ArrayList<Point>> reconCoordLUT_;
   private String settingsKey_;
   private final boolean maxProjection_;


   /**
    * StackResampler constructor.  Sets up matrices used for the transform, and
    * pre-calculates the re-mapped coordinate space.
    *
    * @param mode YX Projection (0), Orthogonal views (1), or full volume (2)
    * @param maxProjection Do a maximum intensity projection if true, otherwise returns
    *                      mean projections.
    * @param theta Angle between coverslip and lightsheet in radians, theta-tilt
    *              in https://amsikking.github.io/SOLS_optimum_tilt/.
    * @param cameraPixelSizeXyUm Size of one (square) camera pixel in the object plane
    *                            in microns.
    * @param sliceDistanceUm Distance (in microns) between two slices of the input stack in the
    *                        object plane.  Distance is measured in the plane parallel with the
    *                        coverslip.
    * @param zPixelShape Number of slices (z planes) in the input stack.
    * @param yPixelShape Image height in pixel number
    * @param xPixelShape Image width in pixel number
    */
   public StackResampler(
              int mode,
              boolean maxProjection,
              double theta,
              double cameraPixelSizeXyUm,
              double sliceDistanceUm,
              int zPixelShape,
              int yPixelShape,
              int xPixelShape) {

      this.mode_ = mode;
      this.maxProjection_ = maxProjection;
      // concat all args to form a settings key
      this.settingsKey_ = createSettingsKey(
              mode, theta, cameraPixelSizeXyUm, sliceDistanceUm,
               zPixelShape, yPixelShape, xPixelShape
      );
      this.reconstructionVoxelSizeUm_ = cameraPixelSizeXyUm;

      reconCoordOffset_ = new double[2];

      double[][] shearMatrix = {
         {1, 0},
         {Math.tan(Math.PI / 2 - theta), 1}
      };

      double[][] rotationMatrix = {
         // working but yields XZ rather than XY view
         //   {-Math.cos(Math.PI / 2 + theta), Math.sin(Math.PI / 2 + theta)},
         //   {-Math.sin(Math.PI / 2 + theta), -Math.cos(Math.PI / 2 + theta)}
         // rotates by 180 degrees around X axis
         // {Math.cos(theta), -Math.sin(theta)},
         // {Math.sin(theta), Math.cos(theta)}

         // this seems to be doing the right thing...
         {-Math.cos(theta), Math.sin(theta)},
         {-Math.sin(theta), -Math.cos(theta)}
      };

      double[][] cameraPixelToUmMatrix = {
         {sliceDistanceUm * Math.sin(theta), 0},
         {0, cameraPixelSizeXyUm}
      };

      double[][] reconPixelToUmMatrix = {
         {this.reconstructionVoxelSizeUm_, 0},
         {0, this.reconstructionVoxelSizeUm_}
      };

      // Invert the reconPixelToUmMatrix
      double[][] inverseReconPixelToUmMatrix = LinearTransformation.invert(reconPixelToUmMatrix);

      // form transformation matrix from image pixels to reconstruction pixels
      double[][] transformationMatrix = LinearTransformation.multiply(inverseReconPixelToUmMatrix,
               rotationMatrix);
      transformationMatrix = LinearTransformation.multiply(transformationMatrix, shearMatrix);
      this.transformationMatrix_ = LinearTransformation.multiply(transformationMatrix,
               cameraPixelToUmMatrix);

      this.cameraImageShape_ = new int[]{zPixelShape, yPixelShape, xPixelShape};

      this.computeRemappedCoordinateSpace();
      this.precomputeCoordTransformLUTs();
      if (!maxProjection_) {
         this.precomputeReconWeightings();
      }

      lineLocks_ = new Object[this.reconImageShape_[0]][this.reconImageShape_[1]];
      for (int i = 0; i < this.reconImageShape_[0]; i++) {
         for (int j = 0; j < this.reconImageShape_[1]; j++) {
            lineLocks_[i][j] = new Object();
         }
      }
   }

   /**
    * Creates a String with values used to create a StackResampler.
    *
    * @param mode YX Projection (0), Orthogonal views (1), or full volume (2)
    * @param theta Angle with optical axis in radians.
    * @param cameraPixelSizeXyUm Size of one (square) camera pixel in the object plane
    *                            in microns.
    * @param sliceDistanceUm Distance (in microns) between two slices of the input stack in the
    *                        object plane.  Distance is measured in the plane parallel with the
    *                        coverslip.
    * @param zPixelShape Number of slices (z planes) in the input stack.
    * @param yPixelShape Image height in pixel number
    * @param xPixelShape Image width in pixel number
    * @return String unique for given input.
    */
   public static String createSettingsKey(
              int mode,
              double theta,
              double cameraPixelSizeXyUm,
              double sliceDistanceUm,
              int zPixelShape,
              int yPixelShape,
              int xPixelShape) {
      return String.format(
                 "%d_%f_%f_%f_%d_%d_%d",
                 mode,
                 theta,
                 cameraPixelSizeXyUm,
                 sliceDistanceUm,
                 zPixelShape,
                 yPixelShape,
                 xPixelShape);
   }

   /**
    * Returns a String unique for this StackResampler.
    * (that also containes information about parameters used to create
    * this StackResampler.
    *
    * @return String unique for this StackResampler
    */
   public String getSettingsKey() {
      return this.settingsKey_;
   }

   private double[] reconCoordsFromCameraCoords(double imageZ, double imageY) {
      double[] reconCoords =  LinearTransformation.multiply(this.transformationMatrix_,
              new double[]{imageZ, imageY});
      // subtract offset
      reconCoords[0] -= this.reconCoordOffset_[0];
      reconCoords[1] -= this.reconCoordOffset_[1];
      return reconCoords;
   }

   private double[] cameraCoordsFromReconCoords(double reconZ, double reconY) {
      double[][] inverseTransform = LinearTransformation.invert(this.transformationMatrix_);

      double[] result = LinearTransformation.multiply(inverseTransform,
              new double[]{reconZ + reconCoordOffset_[0], reconY + reconCoordOffset_[1]});
      return result;
   }

   private void computeRemappedCoordinateSpace() {
      double[][] corners = new double[][] {
         {0, 0},
         {0, this.cameraImageShape_[1]},
         {this.cameraImageShape_[0], 0},
         {this.cameraImageShape_[0], this.cameraImageShape_[1]}
      };

      double[][] transformedCorners = new double[corners.length][];
      for (int i = 0; i < corners.length; i++) {
         transformedCorners[i] = this.reconCoordsFromCameraCoords(corners[i][0], corners[i][1]);
      }

      double[] minTransformedCoordinates = new double[] {Double.MAX_VALUE, Double.MAX_VALUE};
      double[] maxTransformedCoordinates = new double[] {-Double.MAX_VALUE, -Double.MAX_VALUE};

      for (double[] transformedCorner : transformedCorners) {
         minTransformedCoordinates[0] = Math.min(minTransformedCoordinates[0],
                  transformedCorner[0]);
         minTransformedCoordinates[1] = Math.min(minTransformedCoordinates[1],
                  transformedCorner[1]);
         maxTransformedCoordinates[0] = Math.max(maxTransformedCoordinates[0],
                  transformedCorner[0]);
         maxTransformedCoordinates[1] = Math.max(maxTransformedCoordinates[1],
                  transformedCorner[1]);
      }

      reconCoordOffset_[0] = minTransformedCoordinates[0];
      reconCoordOffset_[1] = minTransformedCoordinates[1];

      double[] totalTransformedExtent = new double[] {
         maxTransformedCoordinates[0] - minTransformedCoordinates[0],
         maxTransformedCoordinates[1] - minTransformedCoordinates[1]
      };

      this.reconImageShape_ = new int[] {
         (int) Math.ceil(totalTransformedExtent[0]) + 1, // Z
         (int) Math.ceil(totalTransformedExtent[1]) + 1, // Y
         this.cameraImageShape_[2] // X, x pixels are copied 1 to 1
      };
   }


   private void precomputeCoordTransformLUTs() {
      this.reconCoordLUT_ = new HashMap<>();
      for (int zIndexRecon = 0; zIndexRecon < this.reconImageShape_[0]; zIndexRecon++) {
         for (int yIndexRecon = 0; yIndexRecon < this.reconImageShape_[1]; yIndexRecon++) {
            double[] cameraCoords = this.cameraCoordsFromReconCoords(zIndexRecon, yIndexRecon);
            Point cameraCoordsInteger = new Point((int) Math.round(cameraCoords[0]),
                     (int) Math.round(cameraCoords[1]));

            if (cameraCoordsInteger.x < 0 || cameraCoordsInteger.y < 0
                     || cameraCoordsInteger.x >= this.cameraImageShape_[0]
                     || cameraCoordsInteger.y >= this.cameraImageShape_[1]) {
               continue; // no valid camera coord maps to it, so safe to ignore
            }

            if (!this.reconCoordLUT_.containsKey(cameraCoordsInteger)) {
               this.reconCoordLUT_.put(cameraCoordsInteger, new ArrayList<Point>());
            }
            this.reconCoordLUT_.get(cameraCoordsInteger).add(new Point(zIndexRecon, yIndexRecon));
         }
      }
   }


   private void precomputeReconWeightings() {
      int reconShapeZ = this.reconImageShape_[0];
      int reconShapeY = this.reconImageShape_[1];
      int reconShapeX = this.reconImageShape_[2];

      this.denominatorYXProjection_ = new int[reconShapeY][reconShapeX];
      this.denominatorZXProjection_ = new int[reconShapeZ][reconShapeX];
      this.denominatorYZProjection_ = new int[reconShapeY][reconShapeZ];

      for (int zIndexCamera = 0; zIndexCamera < this.cameraImageShape_[0]; zIndexCamera++) {
         for (int yIndexCamera = 0; yIndexCamera < this.cameraImageShape_[1]; yIndexCamera++) {
            Point cameraCoords = new Point(zIndexCamera, yIndexCamera);
            if (!this.reconCoordLUT_.containsKey(cameraCoords)) {
               continue;
            }
            // add these camera pixels to all recon pixels they map to
            ArrayList<Point> reconCoords = this.reconCoordLUT_.get(cameraCoords);
            if (this.mode_ == ORTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
               for (Point reconCoord : reconCoords) {
                  int reconZIndex = reconCoord.x;
                  int reconYIndex = reconCoord.y;
                  for (int x = 0; x < reconShapeX; x++) {
                     this.denominatorYXProjection_[reconYIndex][x] += 1;
                     this.denominatorZXProjection_[reconZIndex][x] += 1;
                  }
                  for (int x = 0; x < this.cameraImageShape_[2]; x++) {
                     this.denominatorYZProjection_[reconYIndex][reconZIndex] += 1;
                  }
               }
            }
         }
      }

      // avoid division by 0--doesn't matter because these pixels will be 0 anyway
      if (this.mode_ == ORTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
         for (int i = 0; i < reconShapeY; i++) {
            for (int j = 0; j < reconShapeX; j++) {
               if (this.denominatorYXProjection_[i][j] == 0) {
                  this.denominatorYXProjection_[i][j] = 1;
               }
            }
         }
      }

      if (this.mode_ == ORTHOGONAL_VIEWS) {
         for (int i = 0; i < reconShapeZ; i++) {
            for (int j = 0; j < reconShapeX; j++) {
               if (this.denominatorZXProjection_[i][j] == 0) {
                  this.denominatorZXProjection_[i][j] = 1;
               }
            }
         }
         for (int i = 0; i < reconShapeY; i++) {
            for (int j = 0; j < reconShapeZ; j++) {
               if (this.denominatorYZProjection_[i][j] == 0) {
                  this.denominatorYZProjection_[i][j] = 1;
               }
            }
         }
      }

   }

   /**
    * Call this function before any images arrive to initialize the
    * projection and recon arrays.
    */
   public void initializeProjections() {
      int reconImageZShape = this.reconImageShape_[0];
      int reconImageYShape = this.reconImageShape_[1];
      int reconImageXShape = this.reconImageShape_[2];
      if (this.mode_ == YX_PROJECTION || this.mode_ == ORTHOGONAL_VIEWS) {
         if (this.maxProjection_) {
            maxProjectionYX_ = new short[reconImageYShape * reconImageXShape];
            if (this.mode_ == ORTHOGONAL_VIEWS) {
               maxProjectionZX_ = new short[reconImageZShape * reconImageXShape];
               maxProjectionYZ_ = new short[reconImageZShape * reconImageYShape];
            }
         } else {
            sumProjectionYX_ = new int[reconImageYShape][reconImageXShape];
            if (this.mode_ == ORTHOGONAL_VIEWS) {
               sumProjectionZX_ = new int[reconImageZShape][reconImageXShape];
               sumProjectionYZ_ = new int[reconImageYShape][reconImageZShape];
            }
         }
      } else if (this.mode_ == FULL_VOLUME) {
         reconVolumeZYX_ = new short[reconImageZShape][reconImageYShape * reconImageXShape];
      }
   }

   /**
    * Add images only after first calling {@link #initializeProjections() initializeProjections}.
    * It appears that this function is meant for internal use, and that it is
    * preferred to add images using {@link #addToProcessImageQueue(short[], int)}
    * and start processing using {@link #startStackProcessing()}.  If
    * synchronous execution is OK, it should be fine to use this method and signal
    * that no more images will be added using ({@link #finalizeProjections()}
    *
    * @param image array containing pixel data with width and height as set in
    *              the constructor.
    * @param imageSliceIndex z plane number, starting with 0.
    */
   public void addImageToRecons(short[] image, int imageSliceIndex) {
      if (image == null) {
         return;
      }
      // Add to projection/recon
      for (int yIndexCamera = 0; yIndexCamera < this.cameraImageShape_[1]; yIndexCamera++) {
         if (!this.reconCoordLUT_.containsKey(new Point(imageSliceIndex, yIndexCamera))) {
            continue;
         }

         // Where does each line of x pixels belong in the new image?
         List<Point> destCoords = this.reconCoordLUT_.get(new Point(imageSliceIndex, yIndexCamera));
         int cameraImageWidth = this.cameraImageShape_[2];
         for (Point destCoord : destCoords) {
            int reconZ = destCoord.x;
            int reconY = destCoord.y;

            if (this.mode_ == FULL_VOLUME) {
               System.arraycopy(image, yIndexCamera * cameraImageWidth,
                       reconVolumeZYX_[reconZ], reconY * reconImageShape_[2], cameraImageWidth);
            }

            if (this.mode_ == ORTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
               synchronized (lineLocks_[reconZ][reconY]) {
                  for (int reconX = 0; reconX < cameraImageWidth; reconX++) {
                     if (maxProjection_) {
                        maxProjectionYX_[reconY * reconImageShape_[2] + reconX] = (short) Math.max(
                                maxProjectionYX_[reconY * reconImageShape_[2] + reconX] & 0xffff,
                                image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                        if (this.mode_ == ORTHOGONAL_VIEWS) {
                           maxProjectionZX_[reconZ * reconImageShape_[2] + reconX] =
                                    (short) Math.max(maxProjectionZX_[
                                             reconZ * reconImageShape_[2] + reconX] & 0xffff,
                                   image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                           maxProjectionYZ_[reconY * reconImageShape_[0] + reconZ] =
                                    (short) Math.max(maxProjectionYZ_[
                                             reconY * reconImageShape_[0] + reconZ] & 0xffff,
                                   image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                        }
                     } else {
                        sumProjectionYX_[reconY][reconX] += image[
                                 yIndexCamera * cameraImageWidth + reconX] & 0xffff;
                        if (this.mode_ == ORTHOGONAL_VIEWS) {
                           sumProjectionZX_[reconZ][reconX] += image[
                                    yIndexCamera * cameraImageWidth + reconX] & 0xffff;
                           sumProjectionYZ_[reconY][reconZ] += image[
                                    yIndexCamera * cameraImageWidth + reconX] & 0xffff;
                        }
                     }
                  }
               }
            }
         }
      }
   }

   /**
    * Call after all images have arrived to finalize the projections.
    */
   public void finalizeProjections() {
      if (!maxProjection_) {
         // for mean projections, divide by denominator
         if (this.mode_ == YX_PROJECTION) {
            this.meanProjectionYX_ = divideArrays(sumProjectionYX_, this.denominatorYXProjection_);
         }

         if (this.mode_ == ORTHOGONAL_VIEWS) {
            this.meanProjectionZX_ = divideArrays(sumProjectionZX_, this.denominatorZXProjection_);
            this.meanProjectionYZ_ = divideArrays(sumProjectionYZ_, this.denominatorYZProjection_);
            this.meanProjectionYX_ = divideArrays(sumProjectionYX_, this.denominatorYXProjection_);
         }
      }
   }

   // This is a helper function that performs element-wise division of two 2D arrays
   private short[] divideArrays(int[][] numerator, int[][] denominator) {
      int height = numerator.length;
      int width = numerator[0].length;
      short[] result = new short[height * width];
      for (int i = 0; i < height; i++) {
         for (int j = 0; j < width; j++) {
            result[j + width * i] = (short) ((numerator[i][j] / denominator[i][j]) & 0xffff);
         }
      }
      return result;
   }

   public double getReconstructionVoxelSizeUm() {
      return this.reconstructionVoxelSizeUm_;
   }

   /**
    * Returns YX projection.  Only call after first calling {@link #finalizeProjections()}.
    *
    * @return YX Projection, either maximum intensity or an average projection.
    */
   public short[] getYXProjection() {
      return maxProjection_ ? maxProjectionYX_ : meanProjectionYX_;
   }

   /**
    * Returns ZY projection.  Only call after first calling {@link #finalizeProjections()}.
    *
    * @return ZY Projection, either maximum intensity or an average projection.
    */
   public short[] getYZProjection() {
      return maxProjection_ ? maxProjectionYZ_ : meanProjectionYZ_;
   }

   /**
    * Returns ZX projection.  Only call after first calling {@link #finalizeProjections()}.
    *
    * @return Zx Projection, either maximum intensity or an average projection.
    */
   public short[] getZXProjection() {
      return maxProjection_ ? maxProjectionZX_ : meanProjectionZX_;
   }

   /**
    * Returns reconstructed volume.  Only call after first calling {@link #finalizeProjections()}.
    *
    * @return Reconstructed volume.
    */
   public short[][] getReconstructedVolumeZYX() {
      return reconVolumeZYX_;
   }

   /**
    * Returns the width of the resampled volume in pixels.
    *
    * @return Width of the resampled volume in pixels.
    */
   public int getResampledShapeX() {
      return reconImageShape_[2];
   }

   /**
    * Returns the height  of the resampled volume.
    *
    * @return Height of the resampled volume in pixels.
    */
   public int getResampledShapeY() {
      return reconImageShape_[1];
   }

   /**
    * Returns the number of frames of the resampled volume.
    *
    * @return Number of frames of the resampled volume.
    */
   public int getResampledShapeZ() {
      return reconImageShape_[0];
   }

   /**
    * Use this function to add Tagged images to the processing queue.
    * Processing is started with a call to {@link #startStackProcessing()}.
    * Processing can (and should be) started before images are added
    * to the queue.  The only tag in the TaggedImage that matters is the tag
    * "Z", containing the frame index as an integer starting at zero.
    *
    * @param image TaggedImage containing pixel data of type short[], and the tag
    *              "Z" with the frame index.
    */
   @Deprecated
   public void addToProcessImageQueue(TaggedImage image) {
      try {
         imageQueue_.put(new ImagePlusSlice((short[]) image.pix,
                  (Integer) AcqEngMetadata.getAxes(image.tags).get(AcqEngMetadata.Z_AXIS)));
      } catch (InterruptedException e) {
         e.printStackTrace();
         throw new RuntimeException(e);
      }
   }

   /**
    * Use this function to add Tagged images to the processing queue.
    * Processing is started with a call to {@link #startStackProcessing()}.
    * Processing can (and should be) started before images are added
    * to the queue.  The only tag in the TaggedImage that matters is the tag
    * "Z", containing the frame index as an integer starting at zero.
    *
    * @param image TaggedImage containg pixel data of type short[], and the tag
    *              "Z" with the frame index.
    */
   public void addToProcessImageQueue(short[] image, int sliceIndex) {
      try {
         imageQueue_.put(new ImagePlusSlice(image, sliceIndex));
      } catch (InterruptedException e) {
         e.printStackTrace();
         throw new RuntimeException(e);
      }
   }

   /**
    * Pull images from the queue and process them in parallel until
    * a full z stack is processed or a null pix null tags stop signal is received.
    * The future can be gotten when the stack is finished processing
    */
   public Runnable startStackProcessing() {
      Iterator<ImagePlusSlice> iterator = new Iterator<ImagePlusSlice>() {
         private final AtomicInteger processedImages_ = new AtomicInteger(0);
         private volatile boolean stop_ = false;

         @Override
         public boolean hasNext() {
            return !stop_ && processedImages_.get() < (StackResampler.this.cameraImageShape_[0] - 1);
         }

         @Override
         public ImagePlusSlice next() {
            try {
               ImagePlusSlice element;
               while ((element = imageQueue_.poll(1, TimeUnit.MILLISECONDS)) == null) {
                  // Wait for non-null elements
               }
               if (element.getPixels() == null) {
                  // This is the last image, stop processing
                  stop_ = true;
                  // returning null causes a null pointer exception soon.
                  //return null;
               }
               processedImages_.incrementAndGet();
               return element;
            } catch (InterruptedException e) {
               throw new RuntimeException(e);
            }
         }
      };

      return () -> StreamSupport.stream(Spliterators.spliterator(iterator,
                        StackResampler.this.cameraImageShape_[0],
            Spliterator.ORDERED | Spliterator.IMMUTABLE | Spliterator.NONNULL), true)
            .forEach(imagePlusSlice ->
                    StackResampler.this.addImageToRecons(imagePlusSlice.getPixels(),
                             imagePlusSlice.getFrameNr()));
   }


   /**
    * Helper class to store pixels and frameNr in one instance.
    */
   public class ImagePlusSlice {
      private final short[] pixels_;
      private final int sliceNr_;

      public ImagePlusSlice(short[] pixels, int sliceNr) {
         pixels_ = pixels;
         sliceNr_ = sliceNr;
      }

      public short[] getPixels() {
         return pixels_;
      }

      public int getFrameNr() {
         return sliceNr_;
      }
   }

   /**
    * Helper class to do matrix calculations.
    */
   public static class LinearTransformation {

      /**
       * Multiplies two matrices.
       *
       * @param firstMatrix input matrix one.
       * @param secondMatrix input matrix two.
       * @return Product of the two input matrices.
       */
      public static double[][] multiply(double[][] firstMatrix, double[][] secondMatrix) {
         int row1 = firstMatrix.length;
         int col1 = firstMatrix[0].length;
         int row2 = secondMatrix.length;
         int col2 = secondMatrix[0].length;

         if (col1 != row2) {
            throw new IllegalArgumentException("Matrix dimensions do not allow multiplication");
         }

         double[][] result = new double[row1][col2];
         for (int i = 0; i < row1; i++) {
            for (int j = 0; j < col2; j++) {
               for (int k = 0; k < col1; k++) {
                  result[i][j] += firstMatrix[i][k] * secondMatrix[k][j];
               }
            }
         }

         return result;
      }

      /**
       * Multiples a matrix with a vector.
       *
       * @param matrix Input matrix.
       * @param vector Input vector.
       * @return Product of inputs.
       */
      public static double[] multiply(double[][] matrix, double[] vector) {
         int row = matrix.length;
         int col = matrix[0].length;

         if (col != vector.length) {
            throw new IllegalArgumentException("Matrix dimensions do not allow multiplication");
         }

         double[] result = new double[row];
         for (int i = 0; i < row; i++) {
            for (int j = 0; j < col; j++) {
               result[i] += matrix[i][j] * vector[j];
            }
         }

         return result;
      }

      /**
       * Inverts a matrix.
       *
       * @param matrix Input matrix.
       * @return Invers of input.
       */
      public static double[][] invert(double[][] matrix) {
         if (matrix.length != 2 || matrix[0].length != 2) {
            throw new IllegalArgumentException("Only 2x2 matrices are supported");
         }

         double a = matrix[0][0];
         double b = matrix[0][1];
         double c = matrix[1][0];
         double d = matrix[1][1];

         double det = a * d - b * c;
         if (det == 0) {
            throw new IllegalArgumentException("Matrix is not invertible");
         }

         double[][] inverse = {
            {d / det, -b / det},
            {-c / det, a / det}
         };

         return inverse;
      }
   }


}