"""
Library for reading multiresolution micro-magellan
"""
import os
import mmap
import numpy as np
import sys
import json
import platform
import dask.array as da
import dask
import warnings


class _MagellanMultipageTiffReader:
    # Class corresponsing to a single multipage tiff file in a Micro-Magellan dataset. Pass the full path of the TIFF to
    # instantiate and call close() when finished
    # TIFF constants
    WIDTH = 256
    HEIGHT = 257
    BITS_PER_SAMPLE = 258
    COMPRESSION = 259
    PHOTOMETRIC_INTERPRETATION = 262
    IMAGE_DESCRIPTION = 270
    STRIP_OFFSETS = 273
    SAMPLES_PER_PIXEL = 277
    ROWS_PER_STRIP = 278
    STRIP_BYTE_COUNTS = 279
    X_RESOLUTION = 282
    Y_RESOLUTION = 283
    RESOLUTION_UNIT = 296
    MM_METADATA = 51123

    # file format constants
    INDEX_MAP_OFFSET_HEADER = 54773648
    INDEX_MAP_HEADER = 3453623
    SUMMARY_MD_HEADER = 2355492

    def __init__(self, tiff_path):
        self.tiff_path = tiff_path
        self.file = open(tiff_path, 'rb')
        if platform.system() == 'Windows':
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, prot=mmap.PROT_READ)
        self.summary_md, self.index_tree, self.first_ifd_offset = self._read_header()
        self.mmap_file.close()
        self.np_memmap = np.memmap(self.file, dtype=np.uint8, mode='r')

        # get important metadata fields
        self.width = self.summary_md['Width']
        self.height = self.summary_md['Height']
        self.dtype = np.uint8 if self.summary_md['PixelType'] == 'GRAY8' else np.uint16

    def close(self):
        self.file.close()

    def _read_header(self):
        """
        :param file:
        :return: dictionary with summary metadata, nested dictionary of byte offsets of TIFF Image File Directories with
        keys [channel_index][z_index][frame_index][position_index], int byte offset of first image IFD
        """
        # read standard tiff header
        if self.mmap_file[:2] == b'\x4d\x4d':
            # Big endian
            if sys.byteorder != 'big':
                raise Exception("Potential issue with mismatched endian-ness")
        elif self.mmap_file[:2] == b'\x49\x49':
            # little endian
            if sys.byteorder != 'little':
                raise Exception("Potential issue with mismatched endian-ness")
        else:
            raise Exception('Endian type not specified correctly')
        if np.frombuffer(self.mmap_file[2:4], dtype=np.uint16)[0] != 42:
            raise Exception('Tiff magic 42 missing')
        first_ifd_offset = np.frombuffer(self.mmap_file[4:8], dtype=np.uint32)[0]

        # read custom stuff: summary md, index map
        index_map_offset_header, index_map_offset = np.frombuffer(self.mmap_file[8:16], dtype=np.uint32)
        if index_map_offset_header != self.INDEX_MAP_OFFSET_HEADER:
            raise Exception('Index map offset header wrong')
        summary_md_header, summary_md_length = np.frombuffer(self.mmap_file[32:40], dtype=np.uint32)
        if summary_md_header != self.SUMMARY_MD_HEADER:
            raise Exception('Index map offset header wrong')
        summary_md = json.loads(self.mmap_file[40:40 + summary_md_length])
        index_map_header, index_map_length = np.frombuffer(
            self.mmap_file[40 + summary_md_length:48 + summary_md_length],
            dtype=np.uint32)
        if index_map_header != self.INDEX_MAP_HEADER:
            raise Exception('Index map header incorrect')
        # get index map as nested list of ints
        index_map_raw = np.reshape(np.frombuffer(self.mmap_file[48 + summary_md_length:48 +
                                    summary_md_length + index_map_length * 20], dtype=np.int32), [-1, 5])
        index_map_keys = index_map_raw[:, :4].view(np.int32)
        index_map_byte_offsets = index_map_raw[:, 4].view(np.uint32)
        #for super fast reading of pixels: skip IFDs alltogether
        entries_per_ifd = 13
        num_entries = np.ones(index_map_byte_offsets.shape) * entries_per_ifd
        num_entries[0] += 4 #first one has 4 extra IFDs
        index_map_pixel_byte_offsets = 2 + num_entries * 12 + 4 + index_map_byte_offsets
        # unpack into a tree (i.e. nested dicts)
        index_tree = {}
        c_indices, z_indices, t_indices, p_indices = [np.unique(index_map_keys[:, i]) for i in range(4)]
        for c_index in c_indices:
            for z_index in z_indices:
                for t_index in t_indices:
                    for p_index in p_indices:
                        entry_index = np.flatnonzero((index_map_keys == np.array([c_index, z_index, t_index, p_index])).all(-1))
                        if entry_index.size != 0:
                            # fill out tree as needed
                            if c_index not in index_tree.keys():
                                index_tree[c_index] = {}
                            if z_index not in index_tree[c_index].keys():
                                index_tree[c_index][z_index] = {}
                            if t_index not in index_tree[c_index][z_index].keys():
                                index_tree[c_index][z_index][t_index] = {}
                            index_tree[c_index][z_index][t_index][p_index] = \
                                            (int(index_map_byte_offsets[entry_index[-1]]), int(index_map_pixel_byte_offsets[entry_index[-1]]))
        return summary_md, index_tree, first_ifd_offset

    def _read(self, start, end):
        """
        Convert to python ints
        """
        return self.np_memmap[int(start):int(end)].tobytes()

    def _read_ifd(self, byte_offset):
        """
        Read image file directory. First two bytes are number of entries (n), next n*12 bytes are individual IFDs, final 4
        bytes are next IFD offset location
        :return: dictionary with fields needed for reading
        """
        num_entries = np.frombuffer(self._read(byte_offset, byte_offset + 2), dtype=np.uint16)[0]
        info = {}
        for i in range(num_entries):
            tag, type = np.frombuffer(self._read(byte_offset + 2 + i * 12, byte_offset + 2 + i * 12 + 4),
                                      dtype=np.uint16)
            count = \
            np.frombuffer(self._read(byte_offset + 2 + i * 12 + 4, byte_offset + 2 + i * 12 + 8), dtype=np.uint32)[0]
            if type == 3 and count == 1:
                value = \
                np.frombuffer(self._read(byte_offset + 2 + i * 12 + 8, byte_offset + 2 + i * 12 + 10), dtype=np.uint16)[
                    0]
            else:
                value = \
                np.frombuffer(self._read(byte_offset + 2 + i * 12 + 8, byte_offset + 2 + i * 12 + 12), dtype=np.uint32)[
                    0]
            # save important tags for reading images
            if tag == self.MM_METADATA:
                info['md_offset'] = value
                info['md_length'] = count
            elif tag == self.STRIP_OFFSETS:
                info['pixel_offset'] = value
            elif tag == self.STRIP_BYTE_COUNTS:
                info['bytes_per_image'] = value
        info['next_ifd_offset'] = np.frombuffer(self._read(byte_offset + num_entries * 12 + 2,
                                                           byte_offset + num_entries * 12 + 6), dtype=np.uint32)[0]
        if 'bytes_per_image' not in info or 'pixel_offset' not in info:
            raise Exception('Missing tags in IFD entry, file may be corrupted')
        return info

    def _read_pixels(self, offset, length, memmapped):
        if self.width * self.height * 2 == length:
            pixel_type = np.uint16
        elif self.width * self.height == length:
            pixel_type = np.uint8
        else:
            raise Exception('Unknown pixel type')

        if memmapped:
            return np.reshape(self.np_memmap[offset:offset + self.height * self.width * (2 if \
                                pixel_type == np.uint16 else 1)].view(pixel_type), (self.height, self.width))
        else:
            pixels = np.frombuffer(self._read(offset, offset + length), dtype=pixel_type)
            return np.reshape(pixels, [self.height, self.width])

    def read_metadata(self, channel_index, z_index, t_index, pos_index):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        ifd_data = self._read_ifd(ifd_offset)
        metadata = json.loads(self._read(ifd_data['md_offset'], ifd_data['md_offset'] + ifd_data['md_length']))
        return metadata

    def read_image(self, channel_index, z_index, t_index, pos_index, read_metadata=False, memmapped=False):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        image = np.reshape(self.np_memmap[pixels_offset: pixels_offset + self.width * self.height *
                                    (2 if self.dtype == np.uint16 else 1)].view(self.dtype), [self.height, self.width])
        if not memmapped:
            image = np.copy(image)
        # image = self._read_pixels(ifd_data['pixel_offset'], ifd_data['bytes_per_image'], memmapped)
        if read_metadata:
            ifd_data = self._read_ifd(ifd_offset)
            metadata = json.loads(self._read(ifd_data['md_offset'], ifd_data['md_offset'] + ifd_data['md_length']))
            return image, metadata
        return image

    def check_ifd(self, channel_index, z_index, t_index, pos_index):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        try:
            ifd_data = self._read_ifd(ifd_offset)
            return True
        except:
            return False

class _MagellanResolutionLevel:

    def __init__(self, path, count, max_count):
        """
        open all tiff files in directory, keep them in a list, and a tree based on image indices
        :param path:
        """
        tiff_names = [os.path.join(path, tiff) for tiff in os.listdir(path) if tiff.endswith('.tif')]
        self.reader_list = []
        self.reader_tree = {}
        #populate list of readers and tree mapping indices to readers
        for tiff in tiff_names:
            print('\rOpening file {} of {}'.format(count+1, max_count), end='')
            count += 1
            reader = _MagellanMultipageTiffReader(tiff)
            self.reader_list.append(reader)
            it = reader.index_tree
            for c in it.keys():
                if c not in self.reader_tree.keys():
                    self.reader_tree[c] = {}
                for z in it[c].keys():
                    if z not in self.reader_tree[c].keys():
                        self.reader_tree[c][z] = {}
                    for t in it[c][z].keys():
                        if t not in self.reader_tree[c][z].keys():
                            self.reader_tree[c][z][t] = {}
                        for p in it[c][z][t].keys():
                            self.reader_tree[c][z][t][p] = reader

    def read_image(self, channel_index=0, z_index=0, t_index=0, pos_index=0, read_metadata=False, memmapped=False):
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.read_image(channel_index, z_index, t_index, pos_index, read_metadata, memmapped)

    def read_metadata(self, channel_index=0, z_index=0, t_index=0, pos_index=0):
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.read_metadata(channel_index, z_index, t_index, pos_index)

    def check_ifd(self, channel_index=0, z_index=0, t_index=0, pos_index=0):
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.check_ifd(channel_index, z_index, t_index, pos_index)

    def close(self):
        for reader in self.reader_list:
            reader.close()


class MagellanDataset:
    """
    Class that opens a Micro-Magellan dataset. Only works for regular acquisitions (i.e. not explore acquisitions)
    """

    def __init__(self, dataset_path, full_res_only=True):
        self.path = dataset_path
        res_dirs = [dI for dI in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, dI))]
        # map from downsample factor to datset
        self.res_levels = {}
        if 'Full resolution' not in res_dirs:
            raise Exception('Couldn\'t find full resolution directory. Is this the correct path to a Magellan dataset?')
        num_tiffs = 0
        count = 0
        for res_dir in res_dirs:
            for file in os.listdir(os.path.join(dataset_path, res_dir)):
                if file.endswith('.tif'):
                    num_tiffs += 1
        for res_dir in res_dirs:
            if full_res_only and res_dir != 'Full resolution':
                continue
            res_dir_path = os.path.join(dataset_path, res_dir)
            res_level = _MagellanResolutionLevel(res_dir_path, count, num_tiffs)
            if res_dir == 'Full resolution':
                #TODO: might want to move this within the resolution level class to facilitate loading pyramids
                self.res_levels[1] = res_level
                # get summary metadata and index tree from full resolution image
                self.summary_metadata = res_level.reader_list[0].summary_md
                if 'ChNames' in self.summary_metadata:
                    #Legacy magellan files--load channel names here
                    legacy_channel_names = True
                    self._channel_names = {ch: i for i, ch in enumerate(self.summary_metadata['ChNames'])}
                else:
                    legacy_channel_names = False
                    self._channel_names = {} #read them from image metadata

                # store some fields explicitly for easy access
                self.dtype = np.uint16 if self.summary_metadata['PixelType'] == 'GRAY16' else np.uint8
                self.pixel_size_xy_um = self.summary_metadata['PixelSize_um']
                self.pixel_size_z_um = self.summary_metadata['z-step_um']
                self.image_width = res_level.reader_list[0].width
                self.image_height = res_level.reader_list[0].height
                self.overlap = np.array([self.summary_metadata['GridPixelOverlapY'], self.summary_metadata['GridPixelOverlapX']])
                self.c_z_t_p_tree = res_level.reader_tree
                # index tree is in c - z - t - p hierarchy, get all used indices to calcualte other orderings
                channel_indices = set(self.c_z_t_p_tree.keys())
                z_indices = set()
                time_indices = set()
                position_indices = set()
                for c in self.c_z_t_p_tree.keys():
                    for z in self.c_z_t_p_tree[c]:
                        z_indices.add(z)
                        for t in self.c_z_t_p_tree[c][z]:
                            time_indices.add(t)
                            for p in self.c_z_t_p_tree[c][z][t]:
                                position_indices.add(p)
                                if c not in self._channel_names and not legacy_channel_names:
                                    self._channel_names[self.read_metadata(channel_index=c, z_index=z, t_index=t, pos_index=p)['Channel']] = c

                #convert to numpy arrays for speed
                self.z_indices = np.array(sorted(z_indices))
                self.channel_indices = np.array(sorted(channel_indices))
                self.time_indices = np.array(sorted(time_indices))
                self.position_indices = np.array(sorted(position_indices))

                # populate tree in a different ordering
                self.p_t_z_c_tree = {}
                for p in self.position_indices:
                    for t in self.time_indices:
                        for z in self.z_indices :
                            for c in self.channel_indices:
                                if z in self.c_z_t_p_tree[c] and t in self.c_z_t_p_tree[c][z] and p in \
                                        self.c_z_t_p_tree[c][z][t]:
                                    if p not in self.p_t_z_c_tree:
                                        self.p_t_z_c_tree[p] = {}
                                    if t not in self.p_t_z_c_tree[p]:
                                        self.p_t_z_c_tree[p][t] = {}
                                    if z not in self.p_t_z_c_tree[p][t]:
                                        self.p_t_z_c_tree[p][t][z] = {}
                                    self.p_t_z_c_tree[p][t][z][c] = self.c_z_t_p_tree[c][z][t][p]

                #Make an n x 2 array with nan's where no positions actually exist
                row_cols = []
                for p_index in range(np.max(self.position_indices) + 1):
                    if p_index in self.p_t_z_c_tree.keys():
                        t_index = list(self.p_t_z_c_tree[p_index].keys())[0]
                        z_index = list(self.p_t_z_c_tree[p_index][t_index].keys())[0]
                        c_index = list(self.p_t_z_c_tree[p_index][t_index][z_index].keys())[0]
                        if not self.has_image(channel_index=c_index, pos_index=p_index, t_index=t_index, z_index=z_index):
                            row_cols.append(np.array([np.nan, np.nan])) #this position is corrupted
                            warnings.warn('Corrupted image p: {} c: {} t: {} z: {}'.format(p_index, c_index, t_index, z_index))
                        else:
                            md = self.read_metadata(channel_index=c_index, pos_index=p_index, t_index=t_index, z_index=z_index)
                            row_cols.append(np.array([md['GridRowIndex'], md['GridColumnIndex']]))
                    else:
                        row_cols.append(np.array([np.nan, np.nan]))
                self.row_col_array = np.stack(row_cols)
            else:
                self.res_levels[int(res_dir.split('x')[1])] = res_level
        print('\rDataset opened')

    def channel_name_to_index(self, channel_name):
        if channel_name not in self._channel_names.keys():
            raise Exception('Invalid channel name')
        return self._channel_names[channel_name]

    def as_stitched_array(self):

        def read_tile(channel_index, t_index, pos_index, z_index):
            if not np.isnan(pos_index) and channel_index in self.c_z_t_p_tree and \
                    z_index in self.c_z_t_p_tree[channel_index] and \
                    t_index in self.c_z_t_p_tree[channel_index][z_index] and \
                    pos_index in self.c_z_t_p_tree[channel_index][z_index][t_index]:
                img = self.read_image(channel_index=channel_index, z_index=z_index, t_index=t_index,
                                      pos_index=pos_index, memmapped=True)
            else:
                img = self._empty_tile
            # crop to center of tile for stitching
            return img[self.half_overlap:-self.half_overlap, self.half_overlap:-self.half_overlap]

        def z_stack(c_index, t_index, p_index):
            if np.isnan(p_index):
                return da.stack(self.z_indices.size * [self._empty_tile[self.half_overlap:-self.half_overlap,
                                  self.half_overlap:-self.half_overlap]])
            else:
                z_list = []
                for z_index in self.z_indices:
                    z_list.append(read_tile(c_index, t_index, p_index, z_index))
                return da.stack(z_list)

        self.half_overlap = self.overlap[0] // 2

        #get spatial layout of position indices
        zero_min_row_col = (self.row_col_array - np.nanmin(self.row_col_array, axis=0))
        row_col_mat = np.nan * np.ones([int(np.nanmax(zero_min_row_col[:, 0])) + 1, int(np.nanmax(zero_min_row_col[:, 1])) + 1])
        rows = zero_min_row_col[self.position_indices][:, 0]
        cols = zero_min_row_col[self.position_indices][:, 1]
        #mask in case some positions were corrupted
        mask = np.logical_not(np.isnan(rows))
        row_col_mat[rows[mask].astype(np.int), cols[mask].astype(np.int)] = self.position_indices[mask]

        total = self.time_indices.size * self.channel_indices.size * row_col_mat.shape[0] * row_col_mat.shape[1]
        count = 1
        stacks = []
        for t_index in self.time_indices:
            stacks.append([])
            for c_index in self.channel_indices:
                blocks = []
                for row in row_col_mat:
                    blocks.append([])
                    for p_index in row:
                        print('\rAdding data chunk {} of {}'.format(count, total), end='')
                        count += 1
                        blocks[-1].append(z_stack(c_index, t_index, p_index))

                stacks[-1].append(da.block(blocks))

        print('\rDask array opened')
        return da.stack(stacks)

    def as_array(self, stitched=False):
        """
        Read all data image data as one big Dask array with dimensions (p, t, c, z, y, x) (default) or (t, c, z, y, x)
        (if stitched argument is set to True). The dask array is made up of memory-mapped numpy arrays, so the dataset
        does not need to be able to fit into RAM. If the data doesn't fully fill out the array (e.g. not every z-slice
        collected at every time point), zeros will be added automatically.

        To convert data into a numpy array, call np.asarray() on the returned result. However, doing so will bring the
        data into RAM, so it may be better to do this on only a slice of the array at a time.

        :param stitched: If true, lay out adjacent tiles next to one another
        :return:
        """
        self._empty_tile = np.zeros((self.image_height, self.image_width), self.dtype)
        if stitched:
            return self.as_stitched_array()
        else: #return tiles stacked on a position axis
            blocks = []
            total = self.time_indices.size * self.channel_indices.size * self.z_indices.size * self.position_indices.size
            count = 1
            for p in self.position_indices:
                blocks.append([])
                for t in self.time_indices:
                    blocks[-1].append([])
                    for c in self.channel_indices:
                        blocks[-1][-1].append([])
                        for z in self.z_indices:
                            print('\rAdding data chunk {} of {}'.format(count, total), end='')
                            count += 1
                            if not np.isnan(p) and c in self.c_z_t_p_tree and z in self.c_z_t_p_tree[c] and \
                                    t in self.c_z_t_p_tree[c][z] and p in self.c_z_t_p_tree[c][z][t]:
                                blocks[-1][-1][-1].append(self.read_image(
                                    channel_index=c, z_index=z, t_index=t, pos_index=p, memmapped=True))
                            else:
                                blocks[-1][-1][-1].append(np.zeros((self.image_height, self.image_width), self.dtype))
            print('Stacking tiles')
            array = da.stack(blocks)
            print('\rDask array opened')
            return array

    def has_image(self, channel_name=None, channel_index=0, z_index=0, t_index=0, pos_index=0, downsample_factor=1):
        """
        Check if this image is present in the dataset
        :param channel_name: Overrides channel index if supplied
        :param channel_index:
        :param z_index:
        :param t_index:
        :param pos_index:
        :param downsample_factor:
        :return:
        """
        if channel_name is not None:
            if channel_name not in self.get_channel_names():
                return False
            channel_index = self.channel_name_to_index(channel_name)
        if channel_index in self.c_z_t_p_tree and z_index in self.c_z_t_p_tree[channel_index] and \
                t_index in self.c_z_t_p_tree[channel_index][z_index] and pos_index in \
                self.c_z_t_p_tree[channel_index][z_index][t_index]:
            res_level = self.res_levels[downsample_factor]
            return res_level.check_ifd(channel_index=channel_index, z_index=z_index, t_index=t_index, pos_index=pos_index)
        return False

    def read_image(self, channel_name=None, channel_index=0, z_index=0, t_index=0, pos_index=0, read_metadata=False,
                   downsample_factor=1, memmapped=False):
        """
        Read image data as numpy array
        :param channel_name: Overrides channel index if supplied
        :param channel_index:
        :param z_index:
        :param t_index:
        :param pos_index:
        :param read_metadata: if True, return a tuple with dict of image metadata as second element
        :param downsample_factor: 1 is full resolution, lower resolutions are powers of 2 if available
        :return: image as 2D numpy array, or tuple with image and image metadata as dict
        """
        if channel_name is not None:
            channel_index = self.channel_name_to_index(channel_name)
        res_level = self.res_levels[downsample_factor]
        return res_level.read_image(channel_index, z_index, t_index, pos_index, read_metadata, memmapped)

    def read_metadata(self, channel_name=None, channel_index=0, z_index=0, t_index=0, pos_index=0, downsample_factor=1):
        """
        Read metadata only. Faster than using read_image to retireve metadata
        :param channel_name: Overrides channel index if supplied
        :param channel_index:
        :param z_index:
        :param t_index:
        :param pos_index:
        :param downsample_factor: 1 is full resolution, lower resolutions are powers of 2 if available
        :return: metadata as dict
        """
        if channel_name is not None:
            channel_index = self.channel_name_to_index(channel_name)
        res_level = self.res_levels[downsample_factor]
        return res_level.read_metadata(channel_index, z_index, t_index, pos_index)

    def close(self):
        for res_level in self.res_levels:
            res_level.close()

    def get_z_slices_at(self, position_index, time_index=0):
        """
        return list of z slice indices (i.e. focal planes) at the given XY position
        :param position_index:
        :return:
        """
        return list(self.p_t_z_c_tree[position_index][time_index].keys())

    def get_min_max_z_index(self):
        """
        get min and max z indices over all positions
        """
        min_z = 1e100
        max_z = -1e000
        for p_index in self.p_t_z_c_tree.keys():
            for t_index in self.p_t_z_c_tree[p_index].keys():
                new_zs = list(self.p_t_z_c_tree[p_index][t_index].keys())
                min_z = min(min_z, *new_zs)
                max_z = max(max_z, *new_zs)
        return min_z, max_z

    def get_num_xy_positions(self):
        """
        :return: total number of xy positons in data set
        """
        return len(list(self.p_t_z_c_tree.keys()))

    def get_channel_names(self):
        return list(self._channel_names.keys())

    def get_num_rows_and_cols(self):
        """
        Note doesn't  work with explore acquisitions because initial position list isn't populated here
        :return: tuple with total number of rows, total number of cols in dataset
        """
        row_col_tuples = [(pos['GridRowIndex'], pos['GridColumnIndex']) for pos in
                          self.summary_metadata['InitialPositionList']]
        row_indices = list(set(row for row, col in row_col_tuples))
        col_indices = list(set(col for row, col in row_col_tuples))
        num_rows = max(row_indices) + 1
        num_cols = max(col_indices) + 1
        return num_rows, num_cols

    def get_num_frames(self):
        frames = set()
        for t_tree in self.p_t_z_c_tree.values():
            frames.update(t_tree.keys())
        return max(frames) + 1