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
from pycromanager.core import Bridge
import struct
from pycromanager.legacy_data import Legacy_NDTiff_Dataset


class _MultipageTiffReader:
    """
    Class corresponsing to a single multipage tiff file in a Micro-Magellan dataset.
    Pass the full path of the TIFF to instantiate and call close() when finished
    """

    # file format constants
    SUMMARY_MD_HEADER = 2355492
    EIGHT_BIT = 0
    SIXTEEN_BIT = 1
    EIGHT_BIT_RGB = 2
    UNCOMPRESSED = 0

    def __init__(self, tiff_path):
        self.tiff_path = tiff_path
        self.file = open(tiff_path, "rb")
        if platform.system() == "Windows":
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            self.mmap_file = mmap.mmap(self.file.fileno(), 0, prot=mmap.PROT_READ)
        self.summary_md, self.first_ifd_offset = self._read_header()
        self.mmap_file.close()
        self.np_memmap = np.memmap(self.file, dtype=np.uint8, mode="r")

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

        # read custom stuff: header, summary md
        # int.from_bytes(self.mmap_file[24:28], sys.byteorder) # should be equal to 483729 starting in version 1
        self._major_version = int.from_bytes(self.mmap_file[12:16], sys.byteorder)

        summary_md_header, summary_md_length = np.frombuffer(self.mmap_file[16:24], dtype=np.uint32)
        if summary_md_header != self.SUMMARY_MD_HEADER:
            raise Exception("Summary metadata header wrong")
        summary_md = json.loads(self.mmap_file[24 : 24 + summary_md_length])
        return summary_md, first_ifd_offset

    def _read(self, start, end):
        """
        convert to python ints
        """
        return self.np_memmap[int(start) : int(end)].tobytes()

    def read_metadata(self, index):
        return json.loads(
            self._read(
                index["metadata_offset"], index["metadata_offset"] + index["metadata_length"]
            )
        )

    def read_image(self, index, memmapped=True):
        if index["pixel_type"] == self.EIGHT_BIT_RGB:
            bytes_per_pixel = 3
            dtype = np.uint8
        elif index["pixel_type"] == self.EIGHT_BIT:
            bytes_per_pixel = 1
            dtype = np.uint8
        elif index["pixel_type"] == self.SIXTEEN_BIT:
            bytes_per_pixel = 2
            dtype = np.uint16
        else:
            raise Exception("unrecognized pixel type")
        width = index["image_width"]
        height = index["image_height"]

        image = np.reshape(
            self.np_memmap[
                index["pixel_offset"] : index["pixel_offset"] + width * height * bytes_per_pixel
            ].view(dtype),
            [height, width, 3] if bytes_per_pixel == 3 else [height, width],
        )
        if not memmapped:
            image = np.copy(image)
        return image


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
        self.index = self._read_index(path)
        tiff_names = [
            os.path.join(path, tiff) for tiff in os.listdir(path) if tiff.endswith(".tif")
        ]
        self._readers_by_filename = {}
        # populate list of readers and tree mapping indices to readers
        for tiff in tiff_names:
            print("\rOpening file {} of {}...".format(count + 1, max_count), end="")
            count += 1
            self._readers_by_filename[tiff.split(os.sep)[-1]] = _MultipageTiffReader(tiff)
        self.summary_metadata = list(self._readers_by_filename.values())[0].summary_md

    def has_image(self, axes):
        key = frozenset(axes.items())
        return key in self.index

    def _read_index(self, path):
        print("\rReading index...          ", end="")
        with open(path + os.sep + "NDTiff.index", "rb") as index_file:
            data = index_file.read()
        entries = {}
        while len(data) > 0:
            index_entry = {}
            (axes_length,) = struct.unpack("I", data[:4])
            axes_str = data[4 : 4 + axes_length].decode("utf-8")
            axes = json.loads(axes_str)
            data = data[4 + axes_length :]
            (filename_length,) = struct.unpack("I", data[:4])
            index_entry["filename"] = data[4 : 4 + filename_length].decode("utf-8")
            data = data[4 + filename_length :]
            (
                index_entry["pixel_offset"],
                index_entry["image_width"],
                index_entry["image_height"],
                index_entry["pixel_type"],
                index_entry["pixel_compression"],
                index_entry["metadata_offset"],
                index_entry["metadata_length"],
                index_entry["metadata_compression"],
            ) = struct.unpack("IIIIIIII", data[:32])
            data = data[32:]
            entries[frozenset(axes.items())] = index_entry
        print("\rFinshed reading index          ", end="")
        return entries

    def read_image(
        self,
        axes,
        memmapped=True,
    ):
        """

        Parameters
        ----------
        axes : dict
        memmapped : bool
             (Default value = False)

        Returns
        -------
        image :
        """
        # determine which reader contains the image
        key = frozenset(axes.items())
        if key not in self.index:
            raise Exception("image with keys {} not present in data set".format(key))
        index = self.index[key]
        reader = self._readers_by_filename[index["filename"]]
        return reader.read_image(index, memmapped)

    def read_metadata(self, axes):
        """

        Parameters
        ----------
        axes : dict

        Returns
        -------
        image_metadata
        """
        key = frozenset(axes.items())
        if key not in self.index:
            raise Exception("image with keys {} not present in data set".format(key))
        index = self.index[key]
        reader = self._readers_by_filename[index["filename"]]
        return reader.read_metadata(index)

    def close(self):
        for reader in self._readers_by_filename.values():
            reader.close()


class Dataset:
    """Class that opens a single NDTiffStorage dataset"""

    _POSITION_AXIS = "position"
    _ROW_AXIS = "roq"
    _COLUMN_AXIS = "column"
    _Z_AXIS = "z"
    _TIME_AXIS = "time"
    _CHANNEL_AXIS = "channel"

    def __new__(cls, dataset_path=None, full_res_only=True, remote_storage=None):
        if dataset_path is None:
            return super(Dataset, cls).__new__(Dataset)
        # Search for Full resolution dir, check for index
        res_dirs = [
            dI for dI in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, dI))
        ]
        if "Full resolution" not in res_dirs:
            raise Exception(
                "Couldn't find full resolution directory. Is this the correct path to a dataset?"
            )
        fullres_path = (
            dataset_path + ("" if dataset_path[-1] == os.sep else os.sep) + "Full resolution"
        )
        if "NDTiff.index" in os.listdir(fullres_path):
            return super(Dataset, cls).__new__(Dataset)
        else:
            obj = Legacy_NDTiff_Dataset.__new__(Legacy_NDTiff_Dataset)
            obj.__init__(dataset_path, full_res_only, remote_storage)
            return obj

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
                self.res_levels[0] = res_level
                # get summary metadata and index tree from full resolution image
                self.summary_metadata = res_level.summary_metadata

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

                self.axes = {}
                for axes_combo in res_level.index.keys():
                    for axis, position in axes_combo:
                        if axis not in self.axes.keys():
                            self.axes[axis] = set()
                        self.axes[axis].add(position)

                # figure out the mapping of channel name to position by reading image metadata
                print("\rReading channel names...", end="")
                if self._CHANNEL_AXIS in self.axes.keys():
                    self._channel_names = {}
                    for key in res_level.index.keys():
                        axes = {axis: position for axis, position in key}
                        if (
                            self._CHANNEL_AXIS in axes.keys()
                            and axes[self._CHANNEL_AXIS] not in self._channel_names.values()
                        ):
                            channel_name = res_level.read_metadata(axes)["Channel"]
                            self._channel_names[channel_name] = axes[self._CHANNEL_AXIS]
                        if len(self._channel_names.values()) == len(self.axes[self._CHANNEL_AXIS]):
                            break
                print("\rFinished reading channel names", end="")

                # remove axes with no variation
                single_axes = [axis for axis in self.axes if len(self.axes[axis]) == 1]
                for axis in single_axes:
                    del self.axes[axis]

                # If the dataset uses XY stitching, map out the row and col indices
                if (
                    "TiledImageStorage" in self.summary_metadata
                    and self.summary_metadata["TiledImageStorage"]
                ):
                    # Make an n x 2 array with nan's where no positions actually exist
                    pass

            else:
                self.res_levels[int(np.log2(int(res_dir.split("x")[1])))] = res_level

        # get information about image width and height, assuming that they are consistent for whole dataset
        # (which isn't strictly neccesary)
        first_index = list(self.res_levels[0].index.values())[0]
        if first_index["pixel_type"] == _MultipageTiffReader.EIGHT_BIT_RGB:
            self.bytes_per_pixel = 3
            self.dtype = np.uint8
        elif first_index["pixel_type"] == _MultipageTiffReader.EIGHT_BIT:
            self.bytes_per_pixel = 1
            self.dtype = np.uint8
        elif first_index["pixel_type"] == _MultipageTiffReader.SIXTEEN_BIT:
            self.bytes_per_pixel = 2
            self.dtype = np.uint16

        self.image_width = first_index["image_width"]
        self.image_height = first_index["image_height"]
        if "GridPixelOverlapX" in self.summary_metadata:
            self._tile_width = self.image_width - self.summary_metadata["GridPixelOverlapX"]
            self._tile_height = self.image_height - self.summary_metadata["GridPixelOverlapY"]

        print("\rDataset opened                ")

    def as_array(self, stitched=False, verbose=True):
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

        w = self.image_height if not stitched else self._tile_width
        h = self.image_height if not stitched else self._tile_height
        self._empty_tile = (
            np.zeros((h, w), self.dtype)
            if self.bytes_per_pixel != 3
            else np.zeros((h, w, 3), self.dtype)
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
                "\rStacking tiles...         "
            )  # extra space otherwise there is no space after the "Adding data chunk {} {}"
        # import time
        # s = time.time()
        array = da.stack(blocks, allow_unknown_chunksizes=False)
        # e = time.time()
        # print(e - s)
        if verbose:
            print("\rDask array opened")
        return array

    def has_image(
        self,
        channel=0,
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
        if self._remote_storage is not None:
            axes = self._bridge.construct_java_object("java.util.HashMap")
            for key in kwargs.keys():
                axes.put(key, kwargs[key])
            if row is not None and col is not None:
                return self._remote_storage.has_tile_by_row_col(axes, resolution_level, row, col)
            else:
                return self._remote_storage.has_image(axes, resolution_level)

        return self.res_levels[0].has_image(
            self._consolidate_axes(channel, channel_name, z, position, time, row, col, kwargs)
        )

    def read_image(
        self,
        channel=0,
        z=None,
        time=None,
        position=None,
        row=None,
        col=None,
        channel_name=None,
        resolution_level=0,
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
        memmapped : bool
             (Default value = False)
        **kwargs :
            names and integer positions of any other axes

        Returns
        -------
        image : numpy array or tuple
            image as a 2D numpy array, or tuple with image and image metadata as dict

        """
        axes = self._consolidate_axes(channel, channel_name, z, position, time, row, col, kwargs)

        if self._remote_storage is not None:
            if memmapped:
                raise Exception("Memory mapping not available for in progress acquisitions")
            java_axes = self._bridge.construct_java_object("java.util.HashMap")
            for key in axes:
                java_axes.put(key, kwargs[key])
            if not self._remote_storage.has_image(java_axes, resolution_level):
                return None
            tagged_image = self._remote_storage.get_image(axes, resolution_level)
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
            return image
        else:
            res_level = self.res_levels[resolution_level]
            return res_level.read_image(axes, memmapped)

    def read_metadata(
        self,
        channel=0,
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
        axes = self._consolidate_axes(channel, channel_name, z, position, time, row, col, kwargs)

        if self._remote_storage is not None:
            java_axes = self._bridge.construct_java_object("java.util.HashMap")
            for key in axes:
                java_axes.put(key, kwargs[key])
            if not self._remote_storage.has_image(java_axes, resolution_level):
                return None
            # TODO: could speed this up a lot on the Java side by only reading metadata instead of pixels too
            return self._remote_storage.get_image(axes, resolution_level).tags

        else:
            res_level = self.res_levels[resolution_level]
            return res_level.read_metadata(axes)

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

    def _consolidate_axes(self, channel, channel_name, z, position, time, row, col, kwargs):
        axes = {}
        if channel is not None:
            axes[self._CHANNEL_AXIS] = channel
        if channel_name is not None:
            axes[self._CHANNEL_AXIS] = self._channel_names[channel_name]
        if z is not None:
            axes[self._Z_AXIS] = z
        if position is not None:
            axes[self._POSITION_AXIS] = position
        if time is not None:
            axes[self._TIME_AXIS] = time
        if row is not None:
            axes[self._ROW_AXIS] = row
        if col is not None:
            axes[self._COLUMN_AXIS] = col
        for other_axis_name in kwargs.keys():
            axes[other_axis_name] = kwargs[other_axis_name]
        return axes
