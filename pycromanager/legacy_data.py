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
import warnings
from pycromanager.bridge import Bridge
import struct


class _MultipageTiffReader:
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
        self.file = open(tiff_path, "rb")
        if platform.system() == "Windows":
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, prot=mmap.PROT_READ)
        self.summary_md, self.index_tree, self.first_ifd_offset = self._read_header()
        self.mmap_file.close()
        self.np_memmap = np.memmap(self.file, dtype=np.uint8, mode="r")

        # get important metadata fields
        self.rgb = "RGB" in self.summary_md["PixelType"]
        self.width = self.summary_md["Width"]
        self.height = self.summary_md["Height"]
        self.dtype = (
            np.uint8
            if self.summary_md["PixelType"] == "GRAY8" or self.summary_md["PixelType"] == "RGB32"
            else np.uint16
        )

    def close(self):
        """ """
        self.file.close()

    def _read_header(self):
        """
        Returns
        -------
        summary metadata : dict
        byte offsets : nested dict
            The byte offsets of TIFF Image File Directories with keys [channel_index][z_index][frame_index][position_index]
        first_image_byte_offset : int
            int byte offset of first image IFD
        """
        # read standard tiff header
        if self.mmap_file[:2] == b"\x4d\x4d":
            # Big endian
            if sys.byteorder != "big":
                raise Exception("Potential issue with mismatched endian-ness")
        elif self.mmap_file[:2] == b"\x49\x49":
            # little endian
            if sys.byteorder != "little":
                raise Exception("Potential issue with mismatched endian-ness")
        else:
            raise Exception("Endian type not specified correctly")
        if np.frombuffer(self.mmap_file[2:4], dtype=np.uint16)[0] != 42:
            raise Exception("Tiff magic 42 missing")
        first_ifd_offset = np.frombuffer(self.mmap_file[4:8], dtype=np.uint32)[0]

        # read custom stuff: summary md, index map
        index_map_offset_header, index_map_offset = np.frombuffer(
            self.mmap_file[8:16], dtype=np.uint32
        )
        if index_map_offset_header != self.INDEX_MAP_OFFSET_HEADER:
            raise Exception("Index map offset header wrong")
        # int.from_bytes(self.mmap_file[24:28], sys.byteorder) # should be equal to 483729 starting in version 1
        self._major_version = int.from_bytes(self.mmap_file[28:32], sys.byteorder)

        summary_md_header, summary_md_length = np.frombuffer(self.mmap_file[32:40], dtype=np.uint32)
        if summary_md_header != self.SUMMARY_MD_HEADER:
            raise Exception("Index map offset header wrong")
        summary_md = json.loads(self.mmap_file[40 : 40 + summary_md_length])
        index_map_header, index_map_length = np.frombuffer(
            self.mmap_file[40 + summary_md_length : 48 + summary_md_length], dtype=np.uint32
        )
        if index_map_header != self.INDEX_MAP_HEADER:
            raise Exception("Index map header incorrect")
        # get index map as nested list of ints
        index_map_raw = np.reshape(
            np.frombuffer(
                self.mmap_file[
                    48 + summary_md_length : 48 + summary_md_length + index_map_length * 20
                ],
                dtype=np.int32,
            ),
            [-1, 5],
        )
        index_map_keys = index_map_raw[:, :4].view(np.int32)
        index_map_byte_offsets = index_map_raw[:, 4].view(np.uint32)
        # If index map contains an offset value of 0, something has gone wrong
        invalid_entries = np.flatnonzero(index_map_byte_offsets == 0)
        if invalid_entries.size > 0:
            warnings.warn("Invalid entires found in index map, file {}".format(self.tiff_path))
        index_map_keys = index_map_keys[index_map_byte_offsets != 0]
        index_map_byte_offsets = index_map_byte_offsets[index_map_byte_offsets != 0]

        # for super fast reading of pixels: skip IFDs alltogether
        entries_per_ifd = 13
        num_entries = np.ones(index_map_byte_offsets.shape) * entries_per_ifd
        # num_entries[0] += 4 #first one has 4 extra IFDs----Not anymore
        index_map_pixel_byte_offsets = 2 + num_entries * 12 + 4 + index_map_byte_offsets
        # unpack into a tree (i.e. nested dicts)
        index_tree = {}
        c_indices, z_indices, t_indices, p_indices = [
            np.unique(index_map_keys[:, i]) for i in range(4)
        ]
        for c_index in c_indices:
            for z_index in z_indices:
                for t_index in t_indices:
                    for p_index in p_indices:
                        entry_index = np.flatnonzero(
                            (index_map_keys == np.array([c_index, z_index, t_index, p_index])).all(
                                -1
                            )
                        )
                        if entry_index.size != 0:
                            # fill out tree as needed
                            if c_index not in index_tree.keys():
                                index_tree[c_index] = {}
                            if z_index not in index_tree[c_index].keys():
                                index_tree[c_index][z_index] = {}
                            if t_index not in index_tree[c_index][z_index].keys():
                                index_tree[c_index][z_index][t_index] = {}
                            index_tree[c_index][z_index][t_index][p_index] = (
                                int(index_map_byte_offsets[entry_index[-1]]),
                                int(index_map_pixel_byte_offsets[entry_index[-1]]),
                            )
        return summary_md, index_tree, first_ifd_offset

    def _read(self, start, end):
        """
        convert to python ints
        """
        return self.np_memmap[int(start) : int(end)].tobytes()

    def _read_ifd(self, byte_offset):
        """
        Read image file directory. First two bytes are number of entries (n), next n*12 bytes are individual IFDs, final 4
        bytes are next IFD offset location

        Parameters
        ----------
        byte_offset :

        Returns
        -------
        dict :
            dictionary with fields needed for reading

        """
        num_entries = np.frombuffer(self._read(byte_offset, byte_offset + 2), dtype=np.uint16)[0]
        info = {}
        for i in range(num_entries):
            tag, type = np.frombuffer(
                self._read(byte_offset + 2 + i * 12, byte_offset + 2 + i * 12 + 4), dtype=np.uint16
            )
            count = np.frombuffer(
                self._read(byte_offset + 2 + i * 12 + 4, byte_offset + 2 + i * 12 + 8),
                dtype=np.uint32,
            )[0]
            if type == 3 and count == 1:
                value = np.frombuffer(
                    self._read(byte_offset + 2 + i * 12 + 8, byte_offset + 2 + i * 12 + 10),
                    dtype=np.uint16,
                )[0]
            else:
                value = np.frombuffer(
                    self._read(byte_offset + 2 + i * 12 + 8, byte_offset + 2 + i * 12 + 12),
                    dtype=np.uint32,
                )[0]
            # save important tags for reading images
            if tag == self.MM_METADATA:
                info["md_offset"] = value
                info["md_length"] = count
            elif tag == self.STRIP_OFFSETS:
                info["pixel_offset"] = value
            elif tag == self.STRIP_BYTE_COUNTS:
                info["bytes_per_image"] = value
        info["next_ifd_offset"] = np.frombuffer(
            self._read(byte_offset + num_entries * 12 + 2, byte_offset + num_entries * 12 + 6),
            dtype=np.uint32,
        )[0]
        if "bytes_per_image" not in info or "pixel_offset" not in info:
            raise Exception("Missing tags in IFD entry, file may be corrupted")
        return info

    # def _read_pixels(self, offset, length, memmapped):
    #     if self.width * self.height * 2 == length:
    #         pixel_type = np.uint16
    #     elif self.width * self.height == length:
    #         pixel_type = np.uint8
    #     else:
    #         raise Exception('Unknown pixel type')
    #
    #     if memmapped:
    #         return np.reshape(self.np_memmap[offset:offset + self.height * self.width * (2 if \
    #                             pixel_type == np.uint16 else 1)].view(pixel_type), (self.height, self.width))
    #     else:
    #         pixels = np.frombuffer(self._read(offset, offset + length), dtype=pixel_type)
    #         return np.reshape(pixels, [self.height, self.width])

    def read_metadata(self, channel_index, z_index, t_index, pos_index):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        ifd_data = self._read_ifd(ifd_offset)
        metadata = json.loads(
            self._read(ifd_data["md_offset"], ifd_data["md_offset"] + ifd_data["md_length"])
        )
        return metadata

    def read_image(
        self, channel_index, z_index, t_index, pos_index, read_metadata=False, memmapped=False
    ):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        image = np.reshape(
            self.np_memmap[
                pixels_offset : pixels_offset
                + self.width
                * self.height
                * (3 if self.rgb else 1)
                * (2 if self.dtype == np.uint16 else 1)
            ].view(self.dtype),
            [self.height, self.width, 3] if self.rgb else [self.height, self.width],
        )
        if not memmapped:
            image = np.copy(image)
        # image = self._read_pixels(ifd_data['pixel_offset'], ifd_data['bytes_per_image'], memmapped)
        if read_metadata:
            ifd_data = self._read_ifd(ifd_offset)
            metadata = json.loads(
                self._read(ifd_data["md_offset"], ifd_data["md_offset"] + ifd_data["md_length"])
            )
            return image, metadata
        return image

    def check_ifd(self, channel_index, z_index, t_index, pos_index):
        ifd_offset, pixels_offset = self.index_tree[channel_index][z_index][t_index][pos_index]
        try:
            ifd_data = self._read_ifd(ifd_offset)
            return True
        except:
            return False


class _ResolutionLevel:
    def __init__(self, path, count, max_count):
        """
        Open all tiff files in directory, keep them in a list, and a tree based on image indices

        Parameters
        ----------
        path : str
        count : int
        max_count : int

        """
        tiff_names = [
            os.path.join(path, tiff) for tiff in os.listdir(path) if tiff.endswith(".tif")
        ]
        self.reader_list = []
        self.reader_tree = {}
        # populate list of readers and tree mapping indices to readers
        for tiff in tiff_names:
            print("\rOpening file {} of {}".format(count + 1, max_count), end="")
            count += 1
            reader = _MultipageTiffReader(tiff)
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

    def read_image(
        self,
        channel_index=0,
        z_index=0,
        t_index=0,
        pos_index=0,
        read_metadata=False,
        memmapped=False,
    ):
        """

        Parameters
        ----------
        channel_index : int
             (Default value = 0)
        z_index : int
             (Default value = 0)
        t_index : int
             (Default value = 0)
        pos_index : int
             (Default value = 0)
        read_metadata : bool
             (Default value = False)
        memmapped : bool
             (Default value = False)

        Returns
        -------
        image :
        """
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.read_image(
            channel_index, z_index, t_index, pos_index, read_metadata, memmapped
        )

    def read_metadata(self, channel_index=0, z_index=0, t_index=0, pos_index=0):
        """

        Parameters
        ----------
        channel_index : int
             (Default value = 0)
        z_index : int
             (Default value = 0)
        t_index : int
             (Default value = 0)
        pos_index : int
             (Default value = 0)

        Returns
        -------
        image_metadata
        """
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.read_metadata(channel_index, z_index, t_index, pos_index)

    def check_ifd(self, channel_index=0, z_index=0, t_index=0, pos_index=0):
        """

        Parameters
        ----------
        channel_index : int
             (Default value = 0)
        z_index : int
             (Default value = 0)
        t_index : int
             (Default value = 0)
        pos_index : int
             (Default value = 0)

        Returns
        -------
        """
        # determine which reader contains the image
        reader = self.reader_tree[channel_index][z_index][t_index][pos_index]
        return reader.check_ifd(channel_index, z_index, t_index, pos_index)

    def close(self):
        for reader in self.reader_list:
            reader.close()


class Legacy_NDTiff_Dataset:
    """Class that opens a single NDTiffStorage dataset (major versions 0 and 1)"""

    _POSITION_AXIS = "position"
    _Z_AXIS = "z"
    _TIME_AXIS = "time"
    _CHANNEL_AXIS = "channel"

    def __init__(self, dataset_path=None, full_res_only=True, remote_storage=None):
        self._tile_width = None
        self._tile_height = None
        if remote_storage is not None:
            # this dataset is a view of an active acquisiiton. The storage exists on the java side
            self._remote_storage = remote_storage
            self._bridge = Bridge()
            smd = self._remote_storage.get_summary_metadata()
            if "GridPixelOverlapX" in smd.keys():
                self._tile_width = smd["Width"] - smd["GridPixelOverlapX"]
                self._tile_height = smd["Height"] - smd["GridPixelOverlapY"]
            return
        else:
            self._remote_storage = None

        self.path = dataset_path
        res_dirs = [
            dI for dI in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, dI))
        ]
        # map from downsample factor to datset
        self.res_levels = {}
        if "Full resolution" not in res_dirs:
            raise Exception(
                "Couldn't find full resolution directory. Is this the correct path to a dataset?"
            )
        num_tiffs = 0
        count = 0
        for res_dir in res_dirs:
            for file in os.listdir(os.path.join(dataset_path, res_dir)):
                if file.endswith(".tif"):
                    num_tiffs += 1
        for res_dir in res_dirs:
            if full_res_only and res_dir != "Full resolution":
                continue
            res_dir_path = os.path.join(dataset_path, res_dir)
            res_level = _ResolutionLevel(res_dir_path, count, num_tiffs)
            if res_dir == "Full resolution":
                # TODO: might want to move this within the resolution level class to facilitate loading pyramids
                self.res_levels[0] = res_level
                # get summary metadata and index tree from full resolution image
                self.summary_metadata = res_level.reader_list[0].summary_md
                self.rgb = res_level.reader_list[0].rgb
                self._channel_names = {}  # read them from image metadata
                self._extra_axes_to_storage_channel = {}

                # store some fields explicitly for easy access
                self.dtype = (
                    np.uint16 if self.summary_metadata["PixelType"] == "GRAY16" else np.uint8
                )
                self.pixel_size_xy_um = self.summary_metadata["PixelSize_um"]
                self.pixel_size_z_um = (
                    self.summary_metadata["z-step_um"]
                    if "z-step_um" in self.summary_metadata
                    else None
                )
                self.image_width = res_level.reader_list[0].width
                self.image_height = res_level.reader_list[0].height
                self.overlap = (
                    np.array(
                        [
                            self.summary_metadata["GridPixelOverlapY"],
                            self.summary_metadata["GridPixelOverlapX"],
                        ]
                    )
                    if "GridPixelOverlapY" in self.summary_metadata
                    else None
                )
                c_z_t_p_tree = res_level.reader_tree
                # the c here refers to super channels, encompassing all non-tzp axes in addition to channels
                # map of axis names to values where data exists
                self.axes = {
                    self._Z_AXIS: set(),
                    self._TIME_AXIS: set(),
                    self._POSITION_AXIS: set(),
                    self._CHANNEL_AXIS: set(),
                }

                # Need to map "super channels", which absorb all non channel/z/time/position axes to channel indices
                # used by underlying storage
                def parse_axes(current_axes, channel_index):
                    non_zpt_axes = {}
                    for axis_name in current_axes:
                        if axis_name not in [
                            self._Z_AXIS,
                            self._TIME_AXIS,
                            self._POSITION_AXIS,
                        ]:
                            if axis_name not in self.axes:
                                self.axes[axis_name] = set()
                            self.axes[axis_name].add(current_axes[axis_name])
                            non_zpt_axes[axis_name] = current_axes[axis_name]

                    self._extra_axes_to_storage_channel[
                        frozenset(non_zpt_axes.items())
                    ] = channel_index
                    return non_zpt_axes

                print("Parsing metadata\r", end="")
                if "Axes_metedata" in os.listdir(dataset_path):
                    # newer version with a metadata file where this is written explicitly
                    with open(
                        dataset_path
                        + (os.sep if dataset_path[-1] != os.sep else "")
                        + "Axes_metedata",
                        "rb",
                    ) as axes_metadata_file:
                        content = axes_metadata_file.read()
                    while len(content) > 0:
                        (flag,) = struct.unpack("i", content[:4])
                        if flag == -1:
                            channel_index, length = struct.unpack("ii", content[4:12])
                            channel_name = content[12 : 12 + length].decode("iso-8859-1")
                            # contains channel name metadata
                            self._channel_names[channel_name] = channel_index
                            content = content[12 + length :]
                        else:
                            channel_index = flag
                            (length,) = struct.unpack("i", content[4:8])
                            # contains super channel metadata
                            other_axes = content[8 : 8 + length].decode("iso-8859-1")
                            current_axes = {
                                axis_pos.split("_")[0]: int(axis_pos.split("_")[1])
                                for axis_pos in other_axes.split("Axis_")
                                if len(axis_pos) > 0
                            }
                            parse_axes(current_axes, channel_index)
                            content = content[8 + length :]
                    # add standard time position z axes as well
                    for c in c_z_t_p_tree.keys():
                        for z in c_z_t_p_tree[c]:
                            self.axes[self._Z_AXIS].add(z)
                            for t in c_z_t_p_tree[c][z]:
                                self.axes[self._TIME_AXIS].add(t)
                                for p in c_z_t_p_tree[c][z][t]:
                                    self.axes[self._POSITION_AXIS].add(p)

                else:
                    # older version of NDTiffStorage, recover by brute force search through image metadata (slow)
                    for c in c_z_t_p_tree.keys():
                        for z in c_z_t_p_tree[c]:
                            self.axes[self._Z_AXIS].add(z)
                            for t in c_z_t_p_tree[c][z]:
                                self.axes[self._TIME_AXIS].add(t)
                                for p in c_z_t_p_tree[c][z][t]:
                                    self.axes[self._POSITION_AXIS].add(p)
                                    if c not in self.axes["channel"]:
                                        metadata = self.res_levels[0].read_metadata(
                                            channel_index=c, z_index=z, t_index=t, pos_index=p
                                        )
                                        current_axes = metadata["Axes"]
                                        non_zpt_axes = parse_axes(current_axes, c)
                                        # make a map of channel names to channel indices
                                        self._channel_names[metadata["Channel"]] = non_zpt_axes[
                                            self._CHANNEL_AXIS
                                        ]
                print("Parsing metadata complete\r", end="")

                # remove axes with no variation
                single_axes = [axis for axis in self.axes if len(self.axes[axis]) == 1]
                for axis in single_axes:
                    del self.axes[axis]

                # If the dataset uses XY stitching, map out the row and col indices
                if "position" in self.axes and "GridPixelOverlapX" in self.summary_metadata:
                    # Make an n x 2 array with nan's where no positions actually exist
                    self.row_col_array = np.ones((len(self.axes["position"]), 2)) * np.nan
                    self.position_centers = np.ones((len(self.axes["position"]), 2)) * np.nan
                    row_cols = []
                    for c_index in c_z_t_p_tree.keys():
                        for z_index in c_z_t_p_tree[c_index].keys():
                            for t_index in c_z_t_p_tree[c_index][z_index].keys():
                                p_indices = c_z_t_p_tree[c_index][z_index][t_index].keys()
                                for p_index in p_indices:
                                    # in case position index doesn't start at 0, pos_index_index is index
                                    # into self.axes['position']
                                    pos_index_index = list(self.axes["position"]).index(p_index)
                                    if not np.isnan(self.row_col_array[pos_index_index, 0]):
                                        # already figured this one out
                                        continue
                                    if not res_level.check_ifd(
                                        channel_index=c_index,
                                        z_index=z_index,
                                        t_index=t_index,
                                        pos_index=p_index,
                                    ):
                                        row_cols.append(
                                            np.array([np.nan, np.nan])
                                        )  # this position is corrupted
                                        warnings.warn(
                                            "Corrupted image p: {} c: {} t: {} z: {}".format(
                                                p_index, c_index, t_index, z_index
                                            )
                                        )
                                        row_cols.append(np.array([np.nan, np.nan]))
                                    else:
                                        md = res_level.read_metadata(
                                            channel_index=c_index,
                                            pos_index=p_index,
                                            t_index=t_index,
                                            z_index=z_index,
                                        )
                                        self.row_col_array[pos_index_index] = np.array(
                                            [md["GridRowIndex"], md["GridColumnIndex"]]
                                        )
                                        self.position_centers[pos_index_index] = np.array(
                                            [
                                                md["XPosition_um_Intended"],
                                                md["YPosition_um_Intended"],
                                            ]
                                        )

            else:
                self.res_levels[int(np.log2(int(res_dir.split("x")[1])))] = res_level

        if "GridPixelOverlapX" in self.summary_metadata:
            self._tile_width = (
                self.summary_metadata["Width"] - self.summary_metadata["GridPixelOverlapX"]
            )
            self._tile_height = (
                self.summary_metadata["Height"] - self.summary_metadata["GridPixelOverlapY"]
            )
        else:
            self._tile_width = self.summary_metadata["Width"]
            self._tile_height = self.summary_metadata["Height"]

        print("\rDataset opened          ")

    def as_array(self, stitched=False, verbose=False):
        """
        Read all data image data as one big Dask array with last two axes as y, x and preceeding axes depending on data.
        The dask array is made up of memory-mapped numpy arrays, so the dataset does not need to be able to fit into RAM.
        If the data doesn't fully fill out the array (e.g. not every z-slice collected at every time point), zeros will
        be added automatically.

        To convert data into a numpy array, call np.asarray() on the returned result. However, doing so will bring the
        data into RAM, so it may be better to do this on only a slice of the array at a time.

        Parameters
        ----------
        stitched : bool
            If true and tiles were acquired in a grid, lay out adjacent tiles next to one another (Default value = False)
        verbose : bool
            If True print updates on progress loading the image
        Returns
        -------
        dataset : dask array
        """
        if self._remote_storage is not None:
            raise Exception("Method not yet implemented for in progress acquisitions")
        w = self.image_width if not stitched else self._tile_width
        h = self.image_height if not stitched else self._tile_height
        self._empty_tile = (
            np.zeros((h, w), self.dtype) if not self.rgb else np.zeros((h, w, 3), self.dtype)
        )
        self._count = 1
        total = np.prod([len(v) for v in self.axes.values()])

        def recurse_axes(loop_axes, point_axes):
            if len(loop_axes.values()) == 0:
                if verbose:
                    print("\rAdding data chunk {} of {}".format(self._count, total), end="")
                self._count += 1
                if None not in point_axes.values() and self.has_image(**point_axes):
                    if stitched:
                        img = self.read_image(**point_axes, memmapped=True)
                        if self.half_overlap[0] != 0:
                            img = img[
                                self.half_overlap[0] : -self.half_overlap[0],
                                self.half_overlap[1] : -self.half_overlap[1],
                            ]
                        return img
                    else:
                        return self.read_image(**point_axes, memmapped=True)
                else:
                    # return np.zeros((self.image_height, self.image_width), self.dtype)
                    return self._empty_tile
            else:
                # do position first because it makes stitching faster
                axis = (
                    "position"
                    if "position" in loop_axes.keys() and stitched
                    else list(loop_axes.keys())[0]
                )
                remaining_axes = loop_axes.copy()
                del remaining_axes[axis]
                if axis == "position" and stitched:
                    # Stitch tiles acquired in a grid
                    self.half_overlap = (self.overlap[0] // 2, self.overlap[1] // 2)

                    # get spatial layout of position indices
                    zero_min_row_col = self.row_col_array - np.nanmin(self.row_col_array, axis=0)
                    row_col_mat = np.nan * np.ones(
                        [
                            int(np.nanmax(zero_min_row_col[:, 0])) + 1,
                            int(np.nanmax(zero_min_row_col[:, 1])) + 1,
                        ]
                    )
                    positions_indices = np.array(list(loop_axes["position"]))
                    rows = zero_min_row_col[positions_indices][:, 0]
                    cols = zero_min_row_col[positions_indices][:, 1]
                    # mask in case some positions were corrupted
                    mask = np.logical_not(np.isnan(rows))
                    row_col_mat[
                        rows[mask].astype(np.int), cols[mask].astype(np.int)
                    ] = positions_indices[mask]

                    blocks = []
                    for row in row_col_mat:
                        blocks.append([])
                        for p_index in row:
                            if verbose:
                                print(
                                    "\rAdding data chunk {} of {}".format(self._count, total),
                                    end="",
                                )
                            valed_axes = point_axes.copy()
                            valed_axes[axis] = int(p_index) if not np.isnan(p_index) else None
                            blocks[-1].append(da.stack(recurse_axes(remaining_axes, valed_axes)))

                    if self.rgb:
                        stitched_array = np.concatenate(
                            [
                                np.concatenate(row, axis=len(blocks[0][0].shape) - 2)
                                for row in blocks
                            ],
                            axis=len(blocks[0][0].shape) - 3,
                        )
                    else:
                        stitched_array = da.block(blocks)
                    return stitched_array
                else:
                    blocks = []
                    for val in loop_axes[axis]:
                        valed_axes = point_axes.copy()
                        valed_axes[axis] = val
                        blocks.append(recurse_axes(remaining_axes, valed_axes))
                    return blocks

        blocks = recurse_axes(self.axes, {})

        if verbose:
            print(
                " Stacking tiles"
            )  # extra space otherwise there is no space after the "Adding data chunk {} {}"
        array = da.stack(blocks)
        if verbose:
            print("\rDask array opened")
        return array

    def _convert_to_storage_axes(self, axes, channel_name=None):
        """Convert an abitrary set of axes to cztp axes as in the underlying storage

        Parameters
        ----------
        axes
        channel_name
        """
        if channel_name is not None:
            if channel_name not in self._channel_names.keys():
                raise Exception("Channel name {} not found".format(channel_name))
            axes[self._CHANNEL_AXIS] = self._channel_names[channel_name]
        if self._CHANNEL_AXIS not in axes:
            axes[self._CHANNEL_AXIS] = 0

        z_index = axes[self._Z_AXIS] if self._Z_AXIS in axes else 0
        t_index = axes[self._TIME_AXIS] if self._TIME_AXIS in axes else 0
        p_index = axes[self._POSITION_AXIS] if self._POSITION_AXIS in axes else 0

        non_zpt_axes = {
            key: axes[key]
            for key in axes.keys()
            if key not in [self._TIME_AXIS, self._POSITION_AXIS, self._Z_AXIS]
        }
        for axis in non_zpt_axes.keys():
            if axis not in self.axes.keys() and axis != "channel":
                raise Exception("Unknown axis: {}".format(axis))
        c_index = self._extra_axes_to_storage_channel[frozenset(non_zpt_axes.items())]
        return c_index, t_index, p_index, z_index

    def has_image(
        self,
        channel=None,
        z=None,
        time=None,
        position=None,
        channel_name=None,
        resolution_level=0,
        row=None,
        col=None,
        **kwargs
    ):
        """Check if this image is present in the dataset

        Parameters
        ----------
        channel : int
            index of the channel, if applicable (Default value = None)
        z : int
            index of z slice, if applicable (Default value = None)
        time : int
            index of the time point, if applicable (Default value = None)
        position : int
            index of the XY position, if applicable (Default value = None)
        channel_name : str
            Name of the channel. Overrides channel index if supplied (Default value = None)
        row : int
            index of tile row for XY tiled datasets (Default value = None)
        col : int
            index of tile col for XY tiled datasets (Default value = None)
        resolution_level :
            0 is full resolution, otherwise represents downampling of pixels
            at 2 ** (resolution_level) (Default value = 0)
        **kwargs
            Arbitrary keyword arguments

        Returns
        -------
        bool :
            indicating whether the dataset has an image matching the specifications
        """
        if channel is not None:
            kwargs["channel"] = channel
        if z is not None:
            kwargs["z"] = z
        if time is not None:
            kwargs["time"] = time
        if position is not None:
            kwargs["position"] = position

        if self._remote_storage is not None:
            axes = self._bridge._construct_java_object("java.util.HashMap")
            for key in kwargs.keys():
                axes.put(key, kwargs[key])
            if row is not None and col is not None:
                return self._remote_storage.has_tile_by_row_col(axes, resolution_level, row, col)
            else:
                return self._remote_storage.has_image(axes, resolution_level)

        if row is not None or col is not None:
            raise Exception("row col lookup not yet implmented for saved datasets")
            # self.row_col_array #TODO: find position index in here

        storage_c_index, t_index, p_index, z_index = self._convert_to_storage_axes(
            kwargs, channel_name=channel_name
        )
        c_z_t_p_tree = self.res_levels[resolution_level].reader_tree
        if (
            storage_c_index in c_z_t_p_tree
            and z_index in c_z_t_p_tree[storage_c_index]
            and t_index in c_z_t_p_tree[storage_c_index][z_index]
            and p_index in c_z_t_p_tree[storage_c_index][z_index][t_index]
        ):
            res_level = self.res_levels[resolution_level]
            return res_level.check_ifd(
                channel_index=storage_c_index, z_index=z_index, t_index=t_index, pos_index=p_index
            )
        return False

    def read_image(
        self,
        channel=None,
        z=None,
        time=None,
        position=None,
        channel_name=None,
        read_metadata=False,
        resolution_level=0,
        row=None,
        col=None,
        memmapped=False,
        **kwargs
    ):
        """
        Read image data as numpy array

        Parameters
        ----------
        channel : int
            index of the channel, if applicable (Default value = None)
        z : int
            index of z slice, if applicable (Default value = None)
        time : int
            index of the time point, if applicable (Default value = None)
        position : int
            index of the XY position, if applicable (Default value = None)
        channel_name :
            Name of the channel. Overrides channel index if supplied (Default value = None)
        row : int
            index of tile row for XY tiled datasets (Default value = None)
        col : int
            index of tile col for XY tiled datasets (Default value = None)
        resolution_level :
            0 is full resolution, otherwise represents downampling of pixels
            at 2 ** (resolution_level) (Default value = 0)
        read_metadata : bool
             (Default value = False)
        memmapped : bool
             (Default value = False)
        **kwargs :
            names and integer positions of any other axes

        Returns
        -------
        image : numpy array or tuple
            image as a 2D numpy array, or tuple with image and image metadata as dict

        """
        if channel is not None:
            kwargs["channel"] = channel
        if z is not None:
            kwargs["z"] = z
        if time is not None:
            kwargs["time"] = time
        if position is not None:
            kwargs["position"] = position

        if self._remote_storage is not None:
            if memmapped:
                raise Exception("Memory mapping not available for in progress acquisitions")
            axes = self._bridge._construct_java_object("java.util.HashMap")
            for key in kwargs.keys():
                axes.put(key, kwargs[key])
            if not self._remote_storage.has_image(axes, resolution_level):
                return None
            if row is not None and col is not None:
                tagged_image = self._remote_storage.get_tile_by_row_col(
                    axes, resolution_level, row, col
                )
            else:
                tagged_image = self._remote_storage.get_image(axes, resolution_level)
            if tagged_image is None:
                return None
            if resolution_level == 0:
                image = np.reshape(
                    tagged_image.pix,
                    newshape=[tagged_image.tags["Height"], tagged_image.tags["Width"]],
                )
                if (self._tile_height is not None) and (self._tile_width is not None):
                    # crop down to just the part that shows (i.e. no overlap)
                    image = image[
                        (image.shape[0] - self._tile_height)
                        // 2 : -(image.shape[0] - self._tile_height)
                        // 2,
                        (image.shape[1] - self._tile_width)
                        // 2 : -(image.shape[1] - self._tile_width)
                        // 2,
                    ]
            else:
                image = np.reshape(tagged_image.pix, newshape=[self._tile_height, self._tile_width])
            if read_metadata:
                return image, tagged_image.tags
            return image

        if row is not None or col is not None:
            raise Exception("row col lookup not yet implmented for saved datasets")
            # self.row_col_array #TODO: find position index in here

        storage_c_index, t_index, p_index, z_index = self._convert_to_storage_axes(
            kwargs, channel_name=channel_name
        )
        res_level = self.res_levels[resolution_level]
        return res_level.read_image(
            storage_c_index, z_index, t_index, p_index, read_metadata, memmapped
        )

    def read_first_image_metadata(self):
        """
        Get the first image metadata in the dataset (according to position along axes).
        This is useful if you want to access the image metadata in a dataset sparse, nonzero azes

        Returns
        -------
        metadata : dict

        """
        cztp_tree = self.res_levels[0].reader_tree
        c = list(cztp_tree.keys())[0]
        z = list(cztp_tree[c].keys())[0]
        t = list(cztp_tree[c][z].keys())[0]
        p = list(cztp_tree[c][z][t].keys())[0]
        return self.res_levels[0].read_metadata(c, z, t, p)

    def read_metadata(
        self,
        channel=None,
        z=None,
        time=None,
        position=None,
        channel_name=None,
        row=None,
        col=None,
        resolution_level=0,
        **kwargs
    ):
        """
        Read metadata only. Faster than using read_image to retrieve metadata

        Parameters
        ----------
        channel : int
            index of the channel, if applicable (Default value = None)
        z : int
            index of z slice, if applicable (Default value = None)
        time : int
            index of the time point, if applicable (Default value = None)
        position : int
            index of the XY position, if applicable (Default value = None)
        channel_name :
            Name of the channel. Overrides channel index if supplied (Default value = None)
        row : int
            index of tile row for XY tiled datasets (Default value = None)
        col : int
            index of tile col for XY tiled datasets (Default value = None)
        resolution_level :
            0 is full resolution, otherwise represents downampling of pixels
            at 2 ** (resolution_level) (Default value = 0)
        **kwargs :
            names and integer positions of any other axes

        Returns
        -------
        metadata : dict

        """
        if channel is not None:
            kwargs["channel"] = channel
        if z is not None:
            kwargs["z"] = z
        if time is not None:
            kwargs["time"] = time
        if position is not None:
            kwargs["position"] = position

        if self._remote_storage is not None:
            # read the tagged image because no funciton in Java API rn for metadata only
            return self.read_image(
                channel=channel,
                z=z,
                time=time,
                position=position,
                channel_name=channel_name,
                read_metadata=True,
                resolution_level=resolution_level,
                row=row,
                col=col,
                **kwargs
            )[1]

        storage_c_index, t_index, p_index, z_index = self._convert_to_storage_axes(
            kwargs, channel_name=channel_name
        )
        res_level = self.res_levels[resolution_level]
        return res_level.read_metadata(storage_c_index, z_index, t_index, p_index)

    def close(self):
        if self._remote_storage is not None:
            # nothing to do, this is handled on the java side
            return
        for res_level in self.res_levels:
            res_level.close()

    def get_channel_names(self):
        if self._remote_storage is not None:
            raise Exception("Not implemented for in progress datasets")
        return self._channel_names.keys()
