import matplotlib.pyplot as plt
import napari
import numpy as np
import tifffile
import time
from scipy.ndimage import affine_transform

class ObliqueStackProcessor:

    def __init__(self, theta, camera_pixel_size_xy_um, z_step_um, z_pixel_shape, y_pixel_shape, x_pixel_shape, bilinear_interpolation=True):
        self.bilinear_interpolation = bilinear_interpolation
        self.theta = theta
        # The x pixel size is fixed by the camera/optics. anchor other pixels sizes to this for isotropic pixels
        self.reconstruction_voxel_size_um = camera_pixel_size_xy_um

        shear_matrix = np.array([[1, 0],
                                 [np.tan(theta), 1]])
        rotation_matrix = np.array([[-np.cos(np.pi / 2 - theta), np.sin(np.pi / 2 - theta)],
                                    [np.sin(np.pi / 2 - theta), np.cos(np.pi / 2 - theta)]])
        camera_pixel_to_um_matrix = np.array([[z_step_um, 0],
                                            [0, camera_pixel_size_xy_um]])
        recon_pixel_to_um_matrix = np.array([[self.reconstruction_voxel_size_um, 0],
                                            [0, self.reconstruction_voxel_size_um]])

        # form transformation matrix from image pixels to reconstruction pixels
        self.transformation_matrix = np.linalg.inv(recon_pixel_to_um_matrix) @ rotation_matrix @ shear_matrix @ camera_pixel_to_um_matrix
        if np.any(self.transformation_matrix < -1e-10):
            # if its not positive, then assumptions of the interpolation are violated
            raise ValueError("Transformation matrix contains negative values")
        self.transformation_matrix[self.transformation_matrix < 0] = 0 # numerical error

        self.camera_shape = (z_pixel_shape, y_pixel_shape, x_pixel_shape)
        self.compute_remapped_coordinate_space()
        self.precompute_coord_transform_LUTs()
        self.precompute_recon_weightings()


    def recon_coords_from_camera_coords(self, image_z, image_y):
        return self.transformation_matrix @ np.array([image_z, image_y]).reshape(2, -1)

    def camera_coords_from_recon_coords(self, recon_z, recon_y):
        return np.linalg.inv(self.transformation_matrix) @ np.array([recon_z, recon_y]).reshape(2, -1)


    def compute_remapped_coordinate_space(self):
        transformed_corners_zy = self.recon_coords_from_camera_coords(*np.array(
            [[0, 0],
            [0, self.camera_shape[1]],
            [self.camera_shape[0], 0],
            [self.camera_shape[0], self.camera_shape[1]]]).T)

        min_transformed_coordinates_zy = np.min(transformed_corners_zy, axis=1)
        max_transformed_coordinate_zy = np.max(transformed_corners_zy, axis=1)

        total_transformed_extent_zy = max_transformed_coordinate_zy - min_transformed_coordinates_zy

        # Figure out the shape of the remapped image
        self.recon_image_shape = [
            int(np.ceil(total_transformed_extent_zy[0])) + 1,
            int(np.ceil(total_transformed_extent_zy[1])) + 1,
            self.camera_shape[2] # x pixels are copied 1 to 1
        ]

    def precompute_coord_transform_LUTs(self):
        # precompute a look up table from the pixel coordinates in camera images to those in the reconstructed image
        self.dest_coord_LUT = np.zeros((self.camera_shape[0] + 1, self.camera_shape[1] + 1, 2), dtype=int)
        self.dest_bilinear_interp_fractions_LUT = np.zeros((*self.camera_shape[:2], 2, 2), dtype=float)

        for z_index_camera in np.arange(self.camera_shape[0]):
            # get the image on the camera at this z slice
            for y_index_camera in np.arange(self.camera_shape[1]):
                # what is the (lower left) coordinate in the reconstructed image that this pixel maps to?
                recon_coords = self.recon_coords_from_camera_coords(z_index_camera, y_index_camera)
                # get the pixel index in the recon index
                recon_coords_integer = recon_coords // 1
                self.dest_coord_LUT[z_index_camera, y_index_camera, :] = recon_coords_integer.ravel()


    def precompute_recon_weightings(self, do_orthogonal_views=True, do_volume=True):
        """
        Precompute the weightings for performing bilinear interpolation in the reconstruction image
        """
        recon_shape_z, recon_shape_y, recon_shape_x = self.recon_image_shape
        self.denominator_yx_projection = np.zeros((recon_shape_y, recon_shape_x), dtype=float)
        self.denominator_zx_projection = np.zeros((recon_shape_z, recon_shape_x), dtype=float)
        self.denominator_zy_projection = np.zeros((recon_shape_z, recon_shape_y), dtype=float)
        self.denominator_recon_volume = np.zeros((recon_shape_z, recon_shape_y, recon_shape_x), dtype=float)

        for z_index_camera in np.arange(self.camera_shape[0]):
            for y_index_camera in np.arange(self.camera_shape[1]):
                # where does each line of x pixels belong in the new image?
                recon_coord = self.dest_coord_LUT[z_index_camera, y_index_camera]
                recon_z_index, recon_y_index = recon_coord

                if do_volume:
                    if self.bilinear_interpolation:
                        # compute the coordinates of next pixel
                        recon_pixel_midpoint = recon_coord + 0.5
                        # tranform back to camera coordinates
                        recon_pixel_midpoint_in_camera_coords = self.camera_coords_from_recon_coords(*recon_pixel_midpoint)
                        # compute the fraction of intensity that goes to current and next pixel
                        camera_coord = np.array([z_index_camera, y_index_camera])
                        # if its greater than 1 or less than 1, then camera pix are oversampled relative to recon pix
                        # for approx same size pix it should range from 0-1
                        # if camera pix are undersampled relative to recon pix, it will never get much above 0.5 and there
                        # will be empty pixels
                        # This is the fraction that should go to the current pixel vs the next one
                        interp_fraction = recon_pixel_midpoint_in_camera_coords.ravel() - (camera_coord - 0.5)
                        interp_fraction[0] = max(0, min(1, interp_fraction[0]))
                        interp_fraction[1] = max(0, min(1, interp_fraction[1]))

                        self.denominator_recon_volume[recon_z_index, recon_y_index] += interp_fraction[0] * interp_fraction[1]
                        self.denominator_recon_volume[recon_z_index, recon_y_index + 1] += interp_fraction[0] * (1 - interp_fraction[1])
                        self.denominator_recon_volume[recon_z_index + 1, recon_y_index] += (1 - interp_fraction[0]) * interp_fraction[1]
                        self.denominator_recon_volume[recon_z_index + 1, recon_y_index + 1] += (1 - interp_fraction[0]) * (1 - interp_fraction[1])
                    else:
                        self.denominator_recon_volume[recon_z_index, recon_y_index, :] += 1


                if do_orthogonal_views:
                    if self.bilinear_interpolation:
                        self.denominator_yx_projection[recon_y_index, :] += interp_fraction[0]
                        self.denominator_yx_projection[recon_y_index + 1, :] += (1 - interp_fraction[0])
                        self.denominator_zx_projection[recon_z_index, :] += interp_fraction[1]
                        self.denominator_zx_projection[recon_z_index + 1, :] += (1 - interp_fraction[1])
                        self.denominator_zy_projection[recon_z_index, recon_y_index] += interp_fraction[0] * interp_fraction[1] * self.camera_shape[2]
                        self.denominator_zy_projection[recon_z_index, recon_y_index + 1] += interp_fraction[0] * (1 - interp_fraction[1]) * self.camera_shape[2]
                        self.denominator_zy_projection[recon_z_index + 1, recon_y_index] += (1 - interp_fraction[0]) * interp_fraction[1] * self.camera_shape[2]
                        self.denominator_zy_projection[recon_z_index + 1, recon_y_index + 1] += (1 - interp_fraction[0]) * (1 - interp_fraction[1]) * self.camera_shape[2]
                    else:
                        # nearest neighbor interp for projections
                        self.denominator_yx_projection[recon_y_index] += 1
                        self.denominator_zx_projection[recon_z_index] += 1
                        self.denominator_zy_projection[recon_z_index, recon_y_index] += self.camera_shape[2]



        # avoid division by 0--doesnt matter because these pixels will be 0 anyway
        if do_orthogonal_views:
            # change the projections to integers for speed. Not much precision is lost
            # self.denominator_yx_projection = self.denominator_yx_projection.astype(np.uint16)
            # self.denominator_zx_projection = self.denominator_zx_projection.astype(np.uint16)
            # self.denominator_zy_projection = self.denominator_zy_projection.astype(np.uint16)
            self.denominator_yx_projection[self.denominator_yx_projection == 0] = 1
            self.denominator_zx_projection[self.denominator_zx_projection == 0] = 1
            self.denominator_zy_projection[self.denominator_zy_projection == 0] = 1
        if do_volume:
            self.denominator_recon_volume = self.denominator_recon_volume.astype(np.uint16)
            self.denominator_recon_volume[self.denominator_recon_volume == 0] = 1

            if self.bilinear_interpolation:
                # compute the weightings for integer multiplication for interpolation
                self.recon_interp_weightings = np.zeros((recon_shape_z, recon_shape_y, 2, 2), dtype=float)
                for z_index_camera in np.arange(self.camera_shape[0]):
                    for y_index_camera in np.arange(self.camera_shape[1]):
                        # get the weight that goes to this pixel from all camera pixels
                        recon_coords = self.dest_coord_LUT[z_index_camera, y_index_camera]
                        # the zeros are because all x weights are same, for now
                        incident_intensities = np.array([[self.denominator_recon_volume[recon_coords[0], recon_coords[1], 0],
                                                 self.denominator_recon_volume[recon_coords[0], recon_coords[1] + 1, 0]],
                                                [self.denominator_recon_volume[recon_coords[0] + 1, recon_coords[1], 0],
                                                 self.denominator_recon_volume[recon_coords[0] + 1, recon_coords[1] + 1, 0]]])

                        # this is the factor to multiply each camera pixel by so that at the end it can be bit shifted
                        # by 2 bytes to get the final value in unit16
                        self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 0] = incident_intensities[0, 0]
                        self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 1] = incident_intensities[0, 1]
                        self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 0] = incident_intensities[1, 0]
                        self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 1] = incident_intensities[1, 1]
                        # self.recon_volume_interp_weightings[z_index_camera, y_index_camera, 0, 0] = int(
                        #     2 ** 8 / incident_intensities[0, 0])
                        # self.recon_volume_interp_weightings[z_index_camera, y_index_camera, 0, 1] = int(
                        #     2 ** 8 / incident_intensities[0, 1])
                        # self.recon_volume_interp_weightings[z_index_camera, y_index_camera, 1, 0] = int(
                        #     2 ** 8 / incident_intensities[1, 0])
                        # self.recon_volume_interp_weightings[z_index_camera, y_index_camera, 1, 1] = int(
                        #     2 ** 8 / incident_intensities[1, 1])



    def make_projections(self, data, do_orthogonal_views=True, do_volume=True):
        recon_image_z_shape, recon_image_y_shape, recon_image_x_shape = self.recon_image_shape
        sum_projection_yx = np.zeros((recon_image_y_shape, recon_image_x_shape), dtype=float)
        sum_projection_zx = np.zeros((recon_image_z_shape, recon_image_x_shape), dtype=float)
        sum_projection_zy = np.zeros((recon_image_z_shape, recon_image_y_shape), dtype=float)
        sum_recon_volume = np.zeros((recon_image_z_shape, recon_image_y_shape, recon_image_x_shape), dtype=float)

        # do the projection/reconstruction
        # iterate through each z slice of the image
        # at each z slice, iterate through each x pixel and copy a line of y pixels to the new image
        for z_index_camera in np.arange(0, self.camera_shape[0], 1):
            image_on_camera = data[z_index_camera]
            for y_index_camera in range(self.camera_shape[1]):
                # where does each line of x pixels belong in the new image?
                recon_z, recon_y = self.dest_coord_LUT[z_index_camera, y_index_camera]
                source_line_of_x_pixels = image_on_camera[y_index_camera]

                if do_volume:
                    if self.bilinear_interpolation:
                        # add to sum, multiplying by appropriate weighting
                        sum_recon_volume[recon_z, recon_y, :] += source_line_of_x_pixels * self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 0]
                        sum_recon_volume[recon_z, recon_y + 1, :] += source_line_of_x_pixels * self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 1]
                        sum_recon_volume[recon_z + 1, recon_y, :] += source_line_of_x_pixels * self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 0]
                        sum_recon_volume[recon_z + 1, recon_y + 1, :] += source_line_of_x_pixels * self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 1]
                    else:
                        sum_recon_volume[recon_z, recon_y, :] += source_line_of_x_pixels
                        sum_recon_volume[recon_z, recon_y + 1, :] += source_line_of_x_pixels

                if do_orthogonal_views:
                    if self.bilinear_interpolation:
                        sum_projection_yx[recon_y, :] += source_line_of_x_pixels * (
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 0] +
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 0])
                        sum_projection_yx[recon_y + 1, :] += source_line_of_x_pixels * (
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 1] +
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 1])

                        sum_projection_zx[recon_z, :] += source_line_of_x_pixels * (
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 0] +
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 1])
                        sum_projection_zx[recon_z + 1, :] += source_line_of_x_pixels * (
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 0] +
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 1, 1])

                        sum_projection_zy[recon_z, recon_y] += np.sum(source_line_of_x_pixels * (
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 0] +
                            self.recon_interp_weightings[z_index_camera, y_index_camera, 0, 1]))
                    else:
                        # add to the projection no weighting because this is nearest neighbor interpolation
                        sum_projection_yx[recon_y, :] += source_line_of_x_pixels
                        sum_projection_zx[recon_z, :] += source_line_of_x_pixels
                        sum_projection_zy[recon_z, recon_y] += np.sum(source_line_of_x_pixels)


        if do_orthogonal_views:
            if self.bilinear_interpolation:
                mean_projection_yx = (sum_projection_yx / self.denominator_yx_projection).astype(np.uint16)
                mean_projection_zx = (sum_projection_zx / self.denominator_zx_projection).astype(np.uint16)
                mean_projection_zy = (sum_projection_zy / self.denominator_zy_projection).astype(np.uint16)
            else:
                mean_projection_yx = (sum_projection_yx / self.denominator_yx_projection).astype(np.uint16)
                mean_projection_zx = (sum_projection_zx / self.denominator_zx_projection).astype(np.uint16)
                mean_projection_zy = (sum_projection_zy / self.denominator_zy_projection).astype(np.uint16)

        if do_volume:
            if self.bilinear_interpolation:
                mean_recon_volume = (sum_recon_volume / 2 ** 8).astype(np.uint16)
            else:
                mean_recon_volume = (sum_recon_volume / self.denominator_recon_volume).astype(np.uint16)


        import napari
        viewer = napari.Viewer()

        viewer.add_image(mean_recon_volume, name='mean_recon_volume', colormap='inferno')
        viewer.add_image(mean_projection_yx, name='mean_projection_yx', colormap='inferno')
        viewer.add_image(mean_projection_zx, name='mean_projection_zx', colormap='inferno')
        viewer.add_image(mean_projection_zy, name='mean_projection_zy', colormap='inferno')





        return mean_projection_yx, mean_projection_zy, mean_projection_zx, mean_recon_volume

def load_demo_data():
    # load a tiff stack
    # tiff_path = r'C:\Users\henry\Desktop\demo_snouty.tif'
    tiff_path = '/Users/henrypinkard/Desktop/rings_test.tif'
    z_step_um = 0.13
    pixel_size_xy_um = 0.116
    theta = 0.46

    # Read the TIFF stack into a NumPy array
    with tifffile.TiffFile(tiff_path) as tif:
        data = tif.asarray()

    # z x y order
    return data, z_step_um, pixel_size_xy_um, theta


def test_slow_version():
    """
    Use numpy and scipy transforms to (slowly) transfor the data
    """

    data, z_step_um, camera_pixel_size_xy_um, theta = load_demo_data()

    shear_matrix = np.array([[1, 0],
                             [np.tan(theta), 1]])
    rotation_matrix = np.array([[-np.cos(np.pi / 2 - theta), np.sin(np.pi / 2 - theta)],
                                [np.sin(np.pi / 2 - theta), np.cos(np.pi / 2 - theta)]])

    image_2d = data.mean(axis=-1)
    # pad the image on all sides

    # apply shear transform to image_2d
    sheared_image_2d = affine_transform(image_2d, np.linalg.inv(shear_matrix),
                                        offset=[0, 0], order=1, mode='constant', cval=0.0, prefilter=True)
    rotated_image_2d = affine_transform(sheared_image_2d, rotation_matrix,
                                        offset=[0, 50], order=1, mode='constant', cval=0.0, prefilter=True)

    transformed_volume = []
    for index in range(data.shape[-1]):
        sheared = affine_transform(data[:, :, index], np.linalg.inv(shear_matrix),
                                   offset=[0, 0], order=1, mode='constant', cval=0.0, prefilter=True)
        rotated = affine_transform(sheared, rotation_matrix,
                                   offset=[0, 50], order=1, mode='constant', cval=0.0, prefilter=True)
        transformed_volume.append(rotated)
    transformed_volume = np.stack(transformed_volume, axis=2)

    viewer = napari.Viewer()
    viewer.add_image(image_2d)
    viewer.add_image(sheared_image_2d)
    viewer.add_image(rotated_image_2d)
    viewer.add_image(transformed_volume)

data, z_step_um, camera_pixel_size_xy_um, theta = load_demo_data()

# test_slow_version()


proc = ObliqueStackProcessor(theta, camera_pixel_size_xy_um, z_step_um, *data.shape, bilinear_interpolation=False)

mean_projection_yx, mean_projection_zy, mean_projection_zx, mean_recon_volume = proc.make_projections(data)

import napari
viewer = napari.Viewer()
viewer.add_image(data, name='raw data', colormap='inferno')
viewer.add_image(mean_projection_yx, name='mean_projection_yx', colormap='inferno')
viewer.add_image(mean_projection_zy, name='mean_projection_zy', colormap='inferno')
viewer.add_image(mean_projection_zx, name='mean_projection_zx', colormap='inferno')
viewer.add_image(mean_recon_volume, name='mean_recon_volume', colormap='inferno')

# viewer.add_image(proc.denominator_yx_projection, name='pixel_count_sum_projection_yx', colormap='inferno')
# viewer.add_image(proc.denominator_zx_projection, name='pixel_count_sum_projection_zx', colormap='inferno')
# viewer.add_image(proc.denominator_zy_projection, name='pixel_count_sum_projection_zy', colormap='inferno')
# viewer.add_image(proc.denominator_recon_volume, name='pixel_count_recon_volume', colormap='inferno')
#
