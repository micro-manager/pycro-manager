package org.micromanager.lightsheet;

import java.awt.Point;
import java.util.ArrayList;
import java.util.List;
import java.util.HashMap;
import java.util.Iterator;
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
   public static final int OTHOGONAL_VIEWS = 1;
   public static final int FULL_VOLUME = 2;
   private final int mode_;


   private final double reconstructionVoxelSizeUm_;
   private final double[][] transformationMatrix_;
   private double[] reconCoordOffset_;
   private final int[] cameraImageShape_;
   private int[] reconImageShape_;

   private int[][] denominatorYXProjection_;
   private int[][] denominatorZXProjection_;
   private int[][] denominatorZYProjection_;
   private short[] meanProjectionYX_;
   private short[] meanProjectionZX_;
   private short[] meanProjectionZY_;
   private final Object[][] lineLocks_;
   int[][] sumProjectionYX_ = null, sumProjectionZY_ = null, sumProjectionZX_ = null;
   short[] maxProjectionYX_ = null, maxProjectionZY_ = null, maxProjectionZX_ = null;
   short[][] reconVolumeZYX_ = null;
   private final BlockingQueue<TaggedImage> imageQueue_ = new LinkedBlockingDeque<>();
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
    * @param theta Angle with optical axis in radians.
    * @param cameraPixelSizeXyUm Size of one (square) camera pixel in the object plane
    *                            in microns.
    * @param zStepUm Distance (in microns) between two slices of the input stack in the object
    *                plane.  Distance is measured in the plane parallel with the coverslip.
    * @param zPixelShape Number of slices (z planes) in the input stack.
    * @param yPixelShape Image height in pixel number
    * @param xPixelShape Image width in pixel number
    */
   public StackResampler(
              int mode,
              boolean maxProjection,
              double theta,
              double cameraPixelSizeXyUm,
              double zStepUm,
              int zPixelShape,
              int yPixelShape,
              int xPixelShape
      ) {

         this.mode_ = mode;
         this.maxProjection_ = maxProjection;
         // concat all args to form a settings key
         this.settingsKey_ = createSettingsKey(
                 mode, theta, cameraPixelSizeXyUm, zStepUm, zPixelShape, yPixelShape, xPixelShape
         );
         this.reconstructionVoxelSizeUm_ = cameraPixelSizeXyUm;

         reconCoordOffset_ = new double[2];

         double[][] shearMatrix = {
                 {1, 0},
                 {Math.tan(Math.PI / 2 - theta), 1}
         };

         double[][] rotationMatrix = {
            // working but inverted
            //   {-Math.cos(Math.PI / 2 + theta), Math.sin(Math.PI / 2 + theta)},
            //   {-Math.sin(Math.PI / 2 + theta), -Math.cos(Math.PI / 2 + theta)}
                {-Math.cos(theta), Math.sin(theta)},
                {-Math.sin(theta), -Math.cos(theta)}
         };

         double[][] cameraPixelToUmMatrix = {
                {zStepUm * Math.sin(theta), 0},
                {0, cameraPixelSizeXyUm}
         };

         double[][] reconPixelToUmMatrix = {
                 {this.reconstructionVoxelSizeUm_, 0},
                 {0, this.reconstructionVoxelSizeUm_}
         };

         // Invert the reconPixelToUmMatrix
         double[][] inverseReconPixelToUmMatrix = LinearTransformation.invert(reconPixelToUmMatrix);

         // form transformation matrix from image pixels to reconstruction pixels
         double[][] transformationMatrix = LinearTransformation.multiply(inverseReconPixelToUmMatrix, rotationMatrix);
         transformationMatrix = LinearTransformation.multiply(transformationMatrix, shearMatrix);
         this.transformationMatrix_ = LinearTransformation.multiply(transformationMatrix, cameraPixelToUmMatrix);

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

      public static String createSettingsKey(
              int mode,
              double theta,
              double cameraPixelSizeXyUm,
              double zStepUm,
              int zPixelShape,
              int yPixelShape,
              int xPixelShape
      ) {
         return String.format(
                 "%d_%f_%f_%f_%d_%d_%d",
                 mode,
                 theta,
                 cameraPixelSizeXyUm,
                 zStepUm,
                 zPixelShape,
                 yPixelShape,
                 xPixelShape
         );
      }

      public String getSettingsKey() {
         return this.settingsKey_;
      }

      public double[] reconCoordsFromCameraCoords(double imageZ, double imageY) {
         double[] reconCoords =  LinearTransformation.multiply(this.transformationMatrix_,
                 new double[]{imageZ, imageY});
         // subtract offset
         reconCoords[0] -= this.reconCoordOffset_[0];
         reconCoords[1] -= this.reconCoordOffset_[1];
         return reconCoords;
      }

      public double[] cameraCoordsFromReconCoords(double reconZ, double reconY) {
         double[][] inverseTransform = LinearTransformation.invert(this.transformationMatrix_);

         double[] result = LinearTransformation.multiply(inverseTransform,
                 new double[]{reconZ + reconCoordOffset_[0], reconY + reconCoordOffset_[1]});
         return result;
      }

      public void computeRemappedCoordinateSpace() {
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
            minTransformedCoordinates[0] = Math.min(minTransformedCoordinates[0], transformedCorner[0]);
            minTransformedCoordinates[1] = Math.min(minTransformedCoordinates[1], transformedCorner[1]);
            maxTransformedCoordinates[0] = Math.max(maxTransformedCoordinates[0], transformedCorner[0]);
            maxTransformedCoordinates[1] = Math.max(maxTransformedCoordinates[1], transformedCorner[1]);
         }

         reconCoordOffset_[0] = minTransformedCoordinates[0];
         reconCoordOffset_[1] = minTransformedCoordinates[1];

         double[] totalTransformedExtent = new double[] {
                 maxTransformedCoordinates[0] - minTransformedCoordinates[0],
                 maxTransformedCoordinates[1] - minTransformedCoordinates[1]
         };

         this.reconImageShape_ = new int[] {
                 (int) Math.ceil(totalTransformedExtent[0]) + 1,
                 (int) Math.ceil(totalTransformedExtent[1]) + 1,
                 this.cameraImageShape_[2] // x pixels are copied 1 to 1
         };
      }


      public void precomputeCoordTransformLUTs() {
         this.reconCoordLUT_ = new HashMap<>();
         for (int zIndexRecon = 0; zIndexRecon < this.reconImageShape_[0]; zIndexRecon++) {
            for (int yIndexRecon = 0; yIndexRecon < this.reconImageShape_[1]; yIndexRecon++) {
               double[] cameraCoords = this.cameraCoordsFromReconCoords(zIndexRecon, yIndexRecon);
               Point cameraCoordsInteger = new Point((int) Math.round(cameraCoords[0]), (int) Math.round(cameraCoords[1]));

               if (cameraCoordsInteger.x < 0 || cameraCoordsInteger.y < 0 ||
                       cameraCoordsInteger.x >= this.cameraImageShape_[0] || cameraCoordsInteger.y >= this.cameraImageShape_[1]) {
                  continue; // no valid camera coord maps to it, so safe to ignore
               }

               if (!this.reconCoordLUT_.containsKey(cameraCoordsInteger)) {
                  this.reconCoordLUT_.put(cameraCoordsInteger, new ArrayList<Point>());
               }
               this.reconCoordLUT_.get(cameraCoordsInteger).add(new Point(zIndexRecon, yIndexRecon));
            }
         }
      }


   public void precomputeReconWeightings() {

      int reconShapeZ = this.reconImageShape_[0];
      int reconShapeY = this.reconImageShape_[1];
      int reconShapeX = this.reconImageShape_[2];

      this.denominatorYXProjection_ = new int[reconShapeY][reconShapeX];
      this.denominatorZXProjection_ = new int[reconShapeZ][reconShapeX];
      this.denominatorZYProjection_ = new int[reconShapeZ][reconShapeY];

      for (int zIndexCamera = 0; zIndexCamera < this.cameraImageShape_[0]; zIndexCamera++) {
         for (int yIndexCamera = 0; yIndexCamera < this.cameraImageShape_[1]; yIndexCamera++) {
            Point cameraCoords = new Point(zIndexCamera, yIndexCamera);
            if (!this.reconCoordLUT_.containsKey(cameraCoords)) {
               continue;
            }
            // add these camera pixels to all recon pixels they map to
            ArrayList<Point> reconCoords = this.reconCoordLUT_.get(cameraCoords);
            if (this.mode_ == OTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
               for (Point reconCoord : reconCoords) {
               int reconZIndex = reconCoord.x;
               int reconYIndex = reconCoord.y;
                  for (int x = 0; x < reconShapeX; x++) {
                     this.denominatorYXProjection_[reconYIndex][x] += 1;
                     this.denominatorZXProjection_[reconZIndex][x] += 1;
                  }
                  for (int x = 0; x < this.cameraImageShape_[2]; x++) {
                     this.denominatorZYProjection_[reconZIndex][reconYIndex] += this.cameraImageShape_[2];
                  }
               }
            }
         }
      }

      // avoid division by 0--doesn't matter because these pixels will be 0 anyway
      if (this.mode_ == OTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
         for (int i = 0; i < reconShapeY; i++) {
            for (int j = 0; j < reconShapeX; j++) {
               if (this.denominatorYXProjection_[i][j] == 0) {
                  this.denominatorYXProjection_[i][j] = 1;
               }
            }
         }
      }

      if (this.mode_ == OTHOGONAL_VIEWS) {
         for (int i = 0; i < reconShapeZ; i++) {
            for (int j = 0; j < reconShapeX; j++) {
               if (this.denominatorZXProjection_[i][j] == 0) {
                  this.denominatorZXProjection_[i][j] = 1;
               }
            }
         }
         for (int i = 0; i < reconShapeZ; i++) {
            for (int j = 0; j < reconShapeY; j++) {
               if (this.denominatorZYProjection_[i][j] == 0) {
                  this.denominatorZYProjection_[i][j] = 1;
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

      if (this.maxProjection_) {
         maxProjectionYX_ = new short[reconImageYShape * reconImageXShape];
         maxProjectionZX_ = new short[reconImageZShape * reconImageXShape];
         maxProjectionZY_ = new short[reconImageZShape * reconImageYShape];
      } else {
         sumProjectionYX_ = new int[reconImageYShape][reconImageXShape];
         sumProjectionZX_ = new int[reconImageZShape][reconImageXShape];
         sumProjectionZY_ = new int[reconImageZShape][reconImageYShape];
      }
      reconVolumeZYX_ = new short[reconImageZShape][reconImageYShape * reconImageXShape];
   }

   /**
    * Add images only after first calling {@link #initializeProjections() initializeProjections}.
    * It appears that this function is meant for internal use, and that it is
    * preferred to add images using {@link #addToProcessImageQueue(TaggedImage)}
    * and start processing using {@link #startStackProcessing()}.  If
    * synchronous execution is OK, it should be fine to use this method and signal
    * that no more images will be added using ({@link #finalizeProjections()}
    *
    * @param image array containing pixel data with width and height as set in
    *              the constructor.
    * @param imageZIndex z plane number, starting with 0.
    */
   public void addImageToRecons(short[] image, int imageZIndex) {
      // Add to projection/recon
      for (int yIndexCamera = 0; yIndexCamera < this.cameraImageShape_[1]; yIndexCamera++) {
         if (!this.reconCoordLUT_.containsKey(new Point(imageZIndex, yIndexCamera))) {
            continue;
         }

         // Where does each line of x pixels belong in the new image?
         List<Point> destCoords = this.reconCoordLUT_.get(new Point(imageZIndex, yIndexCamera));
         int cameraImageWidth = this.cameraImageShape_[2];
         for (Point destCoord : destCoords) {
            int reconZ = destCoord.x;
            int reconY = destCoord.y;

            if (this.mode_ == FULL_VOLUME) {
               System.arraycopy(image, yIndexCamera * cameraImageWidth,
                       reconVolumeZYX_[reconZ], reconY * reconImageShape_[2], cameraImageWidth);
            }

            if (this.mode_ == OTHOGONAL_VIEWS || this.mode_ == YX_PROJECTION) {
               synchronized (lineLocks_[reconZ][reconY]) {
                  for (int reconX = 0; reconX < cameraImageWidth; reconX++) {
                     if (maxProjection_) {
                        maxProjectionYX_[reconY * reconImageShape_[2] + reconX] = (short) Math.max(
                                maxProjectionYX_[reconY * reconImageShape_[2] + reconX] & 0xffff,
                                image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                        if (this.mode_ == OTHOGONAL_VIEWS) {
                           maxProjectionZX_[reconZ * reconImageShape_[2] + reconX] = (short) Math.max(
                                   maxProjectionZX_[reconZ * reconImageShape_[2] + reconX] & 0xffff,
                                   image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                           maxProjectionZY_[reconZ * reconImageShape_[1] + reconY] = (short) Math.max(
                                   maxProjectionZY_[reconZ * reconImageShape_[1] + reconY] & 0xffff,
                                   image[yIndexCamera * cameraImageWidth + reconX] & 0xffff);
                        }
                     } else {
                        sumProjectionYX_[reconY][reconX] += image[yIndexCamera * cameraImageWidth + reconX] & 0xffff;
                        if (this.mode_ == OTHOGONAL_VIEWS) {
                           sumProjectionZX_[reconZ][reconX] += image[yIndexCamera * cameraImageWidth + reconX] & 0xffff;
                           sumProjectionZY_[reconZ][reconY] += image[yIndexCamera * cameraImageWidth + reconX] & 0xffff;
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

         if (this.mode_ == OTHOGONAL_VIEWS) {
            this.meanProjectionZX_ = divideArrays(sumProjectionZX_, this.denominatorZXProjection_);
            this.meanProjectionZY_ = divideArrays(sumProjectionZY_, this.denominatorZYProjection_);
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
    public short[] getZYProjection() {
        return maxProjection_ ? maxProjectionZY_ : meanProjectionZY_;
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

    public int getResampledShapeX() {
        return reconImageShape_[2];
    }

   public int getResampledShapeY() {
      return reconImageShape_[1];
   }

   public int getResampledShapeZ() {
      return reconImageShape_[0];
   }

   public void addToProcessImageQueue(TaggedImage image) {
      try {
         imageQueue_.put(image);
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
   Runnable startStackProcessing() {
      Iterator<TaggedImage> iterator = new Iterator<TaggedImage>() {
         private final AtomicInteger processedImages_ = new AtomicInteger(0);
         private volatile boolean stop_ = false;

         @Override
         public boolean hasNext() {
            return !stop_ && processedImages_.get() < StackResampler.this.cameraImageShape_[0];
         }

         @Override
         public TaggedImage next() {
            try {
               TaggedImage element;
               while ((element = imageQueue_.poll(1, TimeUnit.MILLISECONDS)) == null) {
                  // Wait for non-null elements
               }
               if (element.tags == null && element.pix == null) {
                  // This is the last image, stop processing
                  stop_ = true;
                  return null;
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
            .forEach(taggedImage ->
                    StackResampler.this.addImageToRecons((short[]) taggedImage.pix,
                            (Integer) AcqEngMetadata.getAxes(taggedImage.tags).get(AcqEngMetadata.Z_AXIS)));
   }


   public static class LinearTransformation {

      public static double[][] multiply(double[][] firstMatrix, double[][] secondMatrix) {
         int row1 = firstMatrix.length;
         int col1 = firstMatrix[0].length;
         int row2 = secondMatrix.length;
         int col2 = secondMatrix[0].length;

         if(col1 != row2) {
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

      public static double[] multiply(double[][] matrix, double[] vector) {
         int row = matrix.length;
         int col = matrix[0].length;

         if(col != vector.length) {
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

