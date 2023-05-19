import matplotlib.pyplot as plt
import napari
import numpy as np
import tifffile
import time
from scipy.ndimage import affine_transform

class ObliqueStackProcessor:

    def __init__(self, theta, camera_pixel_size_xy_um, z_step_um, z_pixel_shape, y_pixel_shape, x_pixel_shape):
        self.theta = theta
        self.recon_coord_offset = np.array([0, 0])
        # The x pixel size is fixed by the camera/optics. anchor other pixels sizes to this for isotropic pixels
        self.reconstruction_voxel_size_um = camera_pixel_size_xy_um

        shear_matrix = np.array([[1, 0],
                                 [-np.tan(theta), 1]])
        rotation_matrix = np.array([[-np.cos(np.pi / 2 + theta), np.sin(np.pi / 2 + theta)],
                                    [-np.sin(np.pi / 2 + theta), -np.cos(np.pi / 2 + theta)]])


        camera_pixel_to_um_matrix = np.array([[z_step_um, 0],
                                            [0, camera_pixel_size_xy_um]])
        recon_pixel_to_um_matrix = np.array([[self.reconstruction_voxel_size_um, 0],
                                            [0, self.reconstruction_voxel_size_um]])

        # form transformation matrix from image pixels to reconstruction pixels
        self.transformation_matrix = np.linalg.inv(recon_pixel_to_um_matrix) @ rotation_matrix @ shear_matrix @ camera_pixel_to_um_matrix

        self.camera_shape = (z_pixel_shape, y_pixel_shape, x_pixel_shape)
        self.compute_remapped_coordinate_space()
        self.precompute_coord_transform_LUTs()
        self.precompute_recon_weightings()


    def recon_coords_from_camera_coords(self, image_z, image_y):
        return self.transformation_matrix @ np.array([image_z, image_y]).reshape(2, -1) - self.recon_coord_offset.reshape(2, -1)

    def camera_coords_from_recon_coords(self, recon_z, recon_y):
        recon_coords = np.array([recon_z, recon_y]).reshape(2, -1) + self.recon_coord_offset.reshape(2, -1)
        return np.linalg.inv(self.transformation_matrix) @ recon_coords


    def compute_remapped_coordinate_space(self):
        transformed_corners_zy = self.recon_coords_from_camera_coords(*np.array(
            [[0, 0],
            [0, self.camera_shape[1]],
            [self.camera_shape[0], 0],
            [self.camera_shape[0], self.camera_shape[1]]]).T)

        min_transformed_coordinates_zy = np.min(transformed_corners_zy, axis=1)
        max_transformed_coordinate_zy = np.max(transformed_corners_zy, axis=1)

        self.recon_coord_offset = np.stack([min_transformed_coordinates_zy,
                                            max_transformed_coordinate_zy], axis=1).min(axis=1)

        total_transformed_extent_zy = max_transformed_coordinate_zy - min_transformed_coordinates_zy

        # Figure out the shape of the remapped image
        self.recon_image_shape = [
            int(np.ceil(total_transformed_extent_zy[0])) + 1,
            int(np.ceil(total_transformed_extent_zy[1])) + 1,
            self.camera_shape[2] # x pixels are copied 1 to 1
        ]

    def precompute_coord_transform_LUTs(self):
        # iterate through desintation coords and find its camera pixel source
        self.recon_coord_LUT = {}
        for z_index_recon in np.arange(self.recon_image_shape[0]):
            for y_index_recon in np.arange(self.recon_image_shape[1]):
                camera_coords = self.camera_coords_from_recon_coords(z_index_recon, y_index_recon).ravel()
                # get the pixel index in the recon index
                camera_coords_integer = np.round(camera_coords).astype(int)
                if camera_coords_integer[0] < 0 or camera_coords_integer[1] < 0 or \
                    camera_coords_integer[0] >= self.camera_shape[0] or camera_coords_integer[1] >= self.camera_shape[1]:
                    continue # no valid camera coord maps to it, so safe to ignore
                if tuple(camera_coords_integer) not in self.recon_coord_LUT:
                    self.recon_coord_LUT[tuple(camera_coords_integer)] = [(z_index_recon, y_index_recon)]
                else:
                    self.recon_coord_LUT[tuple(camera_coords_integer)].append((z_index_recon, y_index_recon))

    def precompute_recon_weightings(self, do_orthogonal_views=True, do_volume=True):
        """
        Precompute the weightings for performing interpolation in the reconstruction image
        """
        recon_shape_z, recon_shape_y, recon_shape_x = self.recon_image_shape
        self.denominator_yx_projection = np.zeros((recon_shape_y, recon_shape_x), dtype=float)
        self.denominator_zx_projection = np.zeros((recon_shape_z, recon_shape_x), dtype=float)
        self.denominator_zy_projection = np.zeros((recon_shape_z, recon_shape_y), dtype=float)
        self.denominator_recon_volume = np.zeros((recon_shape_z, recon_shape_y, recon_shape_x), dtype=float)

        for z_index_camera in np.arange(self.camera_shape[0]):
            for y_index_camera in np.arange(self.camera_shape[1]):
                # where does each line of x pixels belong in the new image?
                if (z_index_camera, y_index_camera) not in self.recon_coord_LUT:
                    print('ignoring: ', z_index_camera, y_index_camera)
                    continue
                recon_coords = self.recon_coord_LUT[(z_index_camera, y_index_camera)]
                for recon_coord in recon_coords:
                    recon_z_index, recon_y_index = recon_coord

                    if do_volume:
                        self.denominator_recon_volume[recon_z_index, recon_y_index, :] += 1

                    if do_orthogonal_views:
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
            self.denominator_recon_volume[self.denominator_recon_volume == 0] = 1


    def make_projections(self, data, do_orthogonal_views=True, do_volume=True):
        recon_image_z_shape, recon_image_y_shape, recon_image_x_shape = self.recon_image_shape
        sum_projection_yx = np.zeros((recon_image_y_shape, recon_image_x_shape), dtype=int)
        sum_projection_zx = np.zeros((recon_image_z_shape, recon_image_x_shape), dtype=int)
        sum_projection_zy = np.zeros((recon_image_z_shape, recon_image_y_shape), dtype=int)
        recon_volume = np.zeros((recon_image_z_shape, recon_image_y_shape, recon_image_x_shape), dtype=int)

        # do the projection/reconstruction
        # iterate through each z slice of the image
        # at each z slice, iterate through each x pixel and copy a line of y pixels to the new image
        for z_index_camera in np.arange(0, self.camera_shape[0], 1):
            image_on_camera = data[z_index_camera]
            for y_index_camera in range(self.camera_shape[1]):
                if (z_index_camera, y_index_camera) not in self.recon_coord_LUT:
                    continue
                source_line_of_x_pixels = image_on_camera[y_index_camera]

                # where does each line of x pixels belong in the new image?
                dest_coords = self.recon_coord_LUT[(z_index_camera, y_index_camera)]
                for dest_coord in dest_coords:
                    recon_z, recon_y = dest_coord

                    if do_volume:
                        recon_volume[recon_z, recon_y, :] = source_line_of_x_pixels

                    if do_orthogonal_views:
                        # add to the projection no weighting because this is nearest neighbor interpolation
                        sum_projection_yx[recon_y, :] += source_line_of_x_pixels
                        sum_projection_zx[recon_z, :] += source_line_of_x_pixels
                        sum_projection_zy[recon_z, recon_y] += np.sum(source_line_of_x_pixels)


        if do_orthogonal_views:
            mean_projection_yx = (sum_projection_yx / self.denominator_yx_projection).astype(np.uint16)
            mean_projection_zx = (sum_projection_zx / self.denominator_zx_projection).astype(np.uint16)
            mean_projection_zy = (sum_projection_zy / self.denominator_zy_projection).astype(np.uint16)


        import napari
        viewer = napari.Viewer()

        # viewer.add_image(recon_volume, name='recon_volume', colormap='inferno')

        viewer.add_image(recon_volume.astype(np.uint16), name='mean_recon_volume', colormap='inferno')
        viewer.add_image(mean_projection_yx, name='mean_projection_yx', colormap='inferno')
        viewer.add_image(mean_projection_zx, name='mean_projection_zx', colormap='inferno')
        viewer.add_image(mean_projection_zy, name='mean_projection_zy', colormap='inferno')

        # plot denominators
        viewer.add_image(self.denominator_recon_volume, name='denominator_recon_volume', colormap='inferno')
        viewer.add_image(self.denominator_yx_projection, name='denominator_yx_projection', colormap='inferno')
        viewer.add_image(self.denominator_zx_projection, name='denominator_zx_projection', colormap='inferno')
        viewer.add_image(self.denominator_zy_projection, name='denominator_zy_projection', colormap='inferno')






        return mean_projection_yx, mean_projection_zy, mean_projection_zx, recon_volume

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
        # its backwards for some reason
        data = data[::-1]

    # data = data[::4]
    # z_step_um *= 4

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


proc = ObliqueStackProcessor(theta, camera_pixel_size_xy_um, z_step_um, *data.shape)

mean_projection_yx, mean_projection_zy, mean_projection_zx, recon_volume = proc.make_projections(data)

import napari
viewer = napari.Viewer()
viewer.add_image(data, name='raw data', colormap='inferno')
viewer.add_image(mean_projection_yx, name='mean_projection_yx', colormap='inferno')
viewer.add_image(mean_projection_zy, name='mean_projection_zy', colormap='inferno')
viewer.add_image(mean_projection_zx, name='mean_projection_zx', colormap='inferno')
viewer.add_image(recon_volume, name='mean_recon_volume', colormap='inferno')

# viewer.add_image(proc.denominator_yx_projection, name='pixel_count_sum_projection_yx', colormap='inferno')
# viewer.add_image(proc.denominator_zx_projection, name='pixel_count_sum_projection_zx', colormap='inferno')
# viewer.add_image(proc.denominator_zy_projection, name='pixel_count_sum_projection_zy', colormap='inferno')
# viewer.add_image(proc.denominator_recon_volume, name='pixel_count_recon_volume', colormap='inferno')
#
