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
        self.rgb = self.storage.isRGB()
        self.bytedepth = self.storage.getByteDepth()
        self.numrows = self.storage.getNumRows()
        self.numcols = self.storage.getNumCols()
        self.overlapx = self.storage.getXOverlap()
        self.overlapy = self.storage.getYOverlap()
        self.tilewidth = self.storage.getTileWidth() + self.overlapx
        self.tileheight = self.storage.getTileHeight() + self.overlapy
        numChannels = self.storage.getNumChannels()
        self.pixelsizexy_um = self.storage.getPixelSizeXY()
        self.pixelsizez_um = self.storage.getPixelSizeZ()
        keys = list(self.storage.imageKeys())
        #covnert to python strings
        keys = [str(x) for x in keys]
        indices = [x.split('_') for x in keys]
        self.imagekeys = [tuple([int(x) for x in entry]) for entry in indices]
        channelspresent = set([(int(x[0])) for x in indices])
        position_indices = set([(int(x[3])) for x in indices])
        self.num_positions = len(position_indices)
        self.num_frames = len(set([(int(x[2])) for x in indices]))
        self.slice_limits = (min(set([(int(x[1])) for x in indices])), max(set([(int(x[1])) for x in indices])))
        #dictionary with (row,col) ad key and position index as value
        self.positionindexfromgridcoords = {(int(self.storage.getGridRow(i,0)), int(self.storage.getGridCol(i,0))) : i for i in position_indices }
        self.gridcoordsfrompositionindex = {i : (int(self.storage.getGridRow(i,0)), int(self.storage.getGridCol(i,0))) for i in position_indices }
        self.channelnamesbymagellanindex = [str(self.storage.getChannelName(x)) for x in range(numChannels)]
        #dictionary with channel name as key, channel index as value
        self.channels = {self.channelnamesbymagellanindex[i] : i for i in channelspresent}
        self.channelnames = list(self.channels.keys())


    def get_slice_indices(self, channel_index, frame, position):
        """
        :return: a list of slices collected at the given tile/frame/channel
        """
        return [key[1] for key in self.imagekeys if key[0] == self.channelnames[channel_index] and key[2] == frame and key[3] == position]

    def read_tile(self, channel, row, col, slice=0, frame=0, return_metadata=False):
        """
        Read image pixels of tile in question
        :param channel: name of the channel. Channels present can be queried by calling the getchannels function
        :param row: tile row index
        :param row: tile column index
        :return: numpy array containing image pixels or None if the requested tile isnt in storage
        """
        channelindex = self.channels[channel]
        positionindex = self.positionindexfromgridcoords[(row,col)]

        tagged_image_object = self.storage.getImage(channelindex, slice, frame, positionindex)
        if tagged_image_object is None:
            return None

        if self.rgb:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get8BitData(), np.dtype('>u1')),(self.tileheight, self.tilewidth,4))
            pixels = pixels[:, :, :3] #throw away alpha channel
        elif self.bytedepth == 1:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get8BitData(), np.dtype('>u1')),(self.tileheight, self.tilewidth))
        else:
            pixels = np.reshape(np.frombuffer(tagged_image_object.get16BitPixelsAsByteArray(), np.dtype('>u2')), (self.tileheight, self.tilewidth) )
        if return_metadata:
            metadata = json.loads(str(tagged_image_object.getTags().toString()))
            return pixels, metadata
        else:
            return pixels


