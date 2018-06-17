from py4j.java_gateway import JavaGateway
import numpy as np
import os
import inspect
import json

class MagellanJavaWrapper:

    def __init__(self, magellandatadir):
        lib_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) + os.sep + 'lib'
        self.javagateway = JavaGateway.launch_gateway(classpath=os.sep.join([lib_path, 'Magellan.jar']), javaopts=['-Xmx4096m'], die_on_exit=True)
        self.storage = self.javagateway.jvm.main.java.org.micromanager.plugins.magellan.acq.MultiResMultipageTiffStorage(magellandatadir)
        self.summary_metadata = json.loads(str(self.storage.getSummaryMetadata().toString()))
        self.num_rows = self.storage.getNumRows()
        self.num_cols = self.storage.getNumCols()
        self.overlap_x = self.storage.getXOverlap()
        self.overlap_y = self.storage.getYOverlap()
        self.pixel_size_xy_um = float(self.summary_metadata['PixelSize_um'])
        self.pixel_size_z_um = float(self.summary_metadata['z-step_um'])
        self.tile_width = self.storage.getTileWidth() + self.overlap_x
        self.tile_height = self.storage.getTileHeight() + self.overlap_y
        self.rgb = self.storage.isRGB()
        self.byte_depth = self.storage.getByteDepth()
        #save image keys as tuple of ints (c, z, t, p)
        keys = list(self.storage.imageKeys())
        keys = [str(x) for x in keys]
        indices = [x.split('_') for x in keys]
        self.image_keys = [tuple([int(x) for x in entry]) for entry in indices]
        #parse image keys to get dimensions of dataset
        #channels frames and slices are guaranteed to be between 0 and max, slices can be anything in the range
        position_indices = set([(int(x[3])) for x in indices])
        self.num_positions = len(position_indices)
        self.num_frames = len(set([(int(x[2])) for x in indices]))
        self.slice_limits = (min(set([(int(x[1])) for x in indices])), max(set([(int(x[1])) for x in indices])))
        self.num_channels = len(set([(int(x[0])) for x in indices]))
        #list of channel names in order of index
        self.channel_names = [str(self.storage.getChannelName(x)) for x in range(self.num_channels)]
        #dictionary with position index as key and (row, col) as value
        self.position_index_from_grid_coords = {(int(self.storage.getGridRow(i, 0)), int(self.storage.getGridCol(i, 0))) : i for i in position_indices}
        #dictionary with (row, col) ad key and position index as value
        self.grid_coords_from_position_index = {i: (int(self.storage.getGridRow(i, 0)), int(self.storage.getGridCol(i, 0))) for i in position_indices}


    def get_slice_indices(self, channel_index, frame_index, position_index):
        """
        :return: a list of slices collected at the given tile/frame/channel
        """
        return [key[1] for key in self.image_keys if key[0] == channel_index and key[2] == frame_index and key[3] == position_index]

    def read_tile(self, channel_index=None, z_index=0, time_index=0, position_index=None, row_col_indices=None,
                  channel_name=None, return_metadata=False):
        """
        Read image pixels of tile at given coordinates. Either channel_index or channel_name can be specified
        :param row_col_indices tuple with (row_index, col_index)
        :return: numpy array containing image pixels or None if the requested tile isnt in storage
        """
        #determine channel index
        if channel_index is None and channel_name is None:
            channel_index = 0 #caller doesnt care about channels
        elif channel_index is None and channel_name is not None:
            channel_index = self.channel_names.index(channel_name)
        #determine positon index
        if position_index is None and row_col_indices is None:
            position_index = 0 #caller doesnt care about positions
        elif position_index is None and row_col_indices is not None:
            position_index = self.position_index_from_grid_coords[row_col_indices]

        tagged_image_object = self.storage.getImage(channel_index, z_index, time_index, position_index)
        if tagged_image_object is None:
            return None

        if self.rgb:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get8BitData(), np.dtype('>u1')), (self.tile_height, self.tile_width, 4))
            pixels = pixels[:, :, :3] #throw away alpha channel
        elif self.byte_depth == 1:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get8BitData(), np.dtype('>u1')), (self.tile_height, self.tile_width))
        else:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get16BitPixelsAsByteArray(), np.dtype('>u2')), (self.tile_height, self.tile_width))
        if return_metadata:
            metadata = json.loads(str(tagged_image_object.getTags().toString()))
            return pixels, metadata
        else:
            return pixels


