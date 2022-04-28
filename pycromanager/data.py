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
from pycromanager.bridge import Bridge
import struct
from pycromanager.legacy_data import Legacy_NDTiff_Dataset
import threading


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
        if self._read(0,2) == b"\x4d\x4d":
            # Big endian
            if sys.byteorder != "big":
                raise Exception("Potential issue with mismatched endian-ness")
        elif self._read(0,2) == b"\x49\x49":
            # little endian
            if sys.byteorder != "little":
                raise Exception("Potential issue with mismatched endian-ness")
        else:
            raise Exception("Endian type not specified correctly")
        if np.frombuffer(self._read(2,4), dtype=np.uint16)[0] != 42:
            raise Exception("Tiff magic 42 missing")
        first_ifd_offset = np.frombuffer(self._read(4,8), dtype=np.uint32)[0]

        # read custom stuff: header, summary md
        # int.from_bytes(self.mmap_file[24:28], sys.byteorder) # should be equal to 483729 starting in version 1
        self._major_version = int.from_bytes(self._read(12,16), sys.byteorder)

        summary_md_header, summary_md_length = np.frombuffer(self._read(16,24), dtype=np.uint32)
        if summary_md_header != self.SUMMARY_MD_HEADER:
            raise Exception("Summary metadata header wrong")
        summary_md = json.loads(self._read(24, 24 + summary_md_length))
        return summary_md, first_ifd_offset

    def _read(self, start, end):
        """
        convert to python ints
        """
        self.file.seek(int(start), 0)
        return self.file.read(end - start)
        # return self.np_memmap[int(start) : int(end)].tobytes()

    def read_metadata(self, index):
        return json.loads(
            self._read(
                index["metadata_offset"], index["metadata_offset"] + index["metadata_length"]
            )
        )

    def read_image(self, index, memmapped=False):
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

        if memmapped:
            np_memmap = np.memmap(self.file, dtype=np.uint8, mode="r")
            image = np.reshape(
                np_memmap[
                    index["pixel_offset"] : index["pixel_offset"] + width * height * bytes_per_pixel
                ].view(dtype),
                [height, width, 3] if bytes_per_pixel == 3 else [height, width],
            )
        else:
            image = np.reshape(
                np.frombuffer(self._read(
                index["pixel_offset"], index["pixel_offset"] + width * height * bytes_per_pixel)
                    , dtype=dtype),
                [height, width, 3] if bytes_per_pixel == 3 else [height, width],
            )
        return image


class _ResolutionLevel:
    def __init__(self, path=None, count=None, max_count=None, remote=False, summary_metadata=False):
        """
        Open all tiff files in directory, keep them in a list, and a tree based on image indices

        Parameters
        ----------
        path : str
        count : int
        max_count : int

        """
        self.path_root = path + ("" if path[-1] == os.sep else os.sep)
        if remote:
            self.summary_metadata = summary_metadata
            self.index = {}
            self._readers_by_filename = {}
        else:
            self.index = self.read_index(path)
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

    def add_index_entry(self, data):
        """
        Manually add a single index entry
        :param data: bytes object of a single index entry
        """
        _, axes, index_entry = self.read_single_index_entry(data, self.index)

        if index_entry["filename"] not in self._readers_by_filename:
            self._readers_by_filename[index_entry["filename"]] = _MultipageTiffReader(
                self.path_root + index_entry["filename"]
            )
        return axes, index_entry

    def read_single_index_entry(self, data, entries, position=0):
        index_entry = {}
        (axes_length,) = struct.unpack("I", data[position : position + 4])
        if axes_length == 0:
            warnings.warn(
                "Index appears to not have been properly terminated (the dataset may still work)"
            )
            return None
        axes_str = data[position + 4 : position + 4 + axes_length].decode("utf-8")
        axes = json.loads(axes_str)
        position += axes_length + 4
        (filename_length,) = struct.unpack("I", data[position : position + 4])
        index_entry["filename"] = data[position + 4 : position + 4 + filename_length].decode(
            "utf-8"
        )
        position += 4 + filename_length
        (
            index_entry["pixel_offset"],
            index_entry["image_width"],
            index_entry["image_height"],
            index_entry["pixel_type"],
            index_entry["pixel_compression"],
            index_entry["metadata_offset"],
            index_entry["metadata_length"],
            index_entry["metadata_compression"],
        ) = struct.unpack("IIIIIIII", data[position : position + 32])
        position += 32
        entries[frozenset(axes.items())] = index_entry
        return position, axes, index_entry

    def read_index(self, path):
        print("\rReading index...          ", end="")
        with open(path + os.sep + "NDTiff.index", "rb") as index_file:
            data = index_file.read()
        entries = {}
        position = 0
        while position < len(data):
            print(
                "\rReading index... {:.1f}%       ".format(
                    100 * (1 - (len(data) - position) / len(data))
                ),
                end="",
            )
            entry = self.read_single_index_entry(data, entries, position)
            if entry is None:
                break
            position, axes, index_entry = entry
            if position is None:
                break

        print("\rFinshed reading index          ", end="")
        return entries

    def read_image(
        self,
        axes,
        memmapped=False,
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


### This function outside class to prevent problems with pickling when running them in differnet process


def _storage_monitor_fn(
    dataset, storage_monitor_push_port, connected_event, callback_fn, debug=False
):
    #TODO: might need to add in support for doing this on a different port, if Acquistiion/bridge is not on default port
    bridge = Bridge()
    monitor_socket = bridge._connect_pull(storage_monitor_push_port)

    connected_event.set()

    while True:
        message = monitor_socket.receive()

        if "finished" in message:
            # Poison, time to shut down
            monitor_socket.close()
            return

        index_entry = message["index_entry"]
        axes = dataset._add_index_entry(index_entry)
        dataset.new_image_arrived = True

        if callback_fn is not None:
            callback_fn(axes, dataset)


class Dataset:
    """Class that opens a single NDTiffStorage dataset"""

    _POSITION_AXIS = "position"
    _ROW_AXIS = "row"
    _COLUMN_AXIS = "column"
    _Z_AXIS = "z"
    _TIME_AXIS = "time"
    _CHANNEL_AXIS = "channel"

    def __new__(cls, dataset_path=None, full_res_only=True, remote_storage_monitor=None):
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
            obj.__init__(dataset_path, full_res_only, remote_storage=None)
            return obj

    def __init__(self, dataset_path=None, full_res_only=True, remote_storage_monitor=None):
        """
        Creat a Object providing access to and NDTiffStorage dataset, either one currently being acquired or one on disk

        Parameters
        ----------
        dataset_path : str
            Abosolute path of top level folder of a dataset on disk
        full_res_only : bool
            One open the full resolution data, if it is multi-res
        remote_storage_monitor : JavaObjectShadow
            Object that allows callbacks from remote NDTiffStorage
        """
        self._tile_width = None
        self._tile_height = None
        self._lock = threading.Lock()
        if remote_storage_monitor is not None:
            # this dataset is a view of an active acquisiiton. The storage exists on the java side
            self.new_image_arrived = False # used by napari viewer to check for updates. Will be reset to false by them
            self._remote_storage_monitor = remote_storage_monitor
            self.summary_metadata = self._remote_storage_monitor.get_summary_metadata()
            if "GridPixelOverlapX" in self.summary_metadata.keys():
                self._tile_width = (
                    self.summary_metadata["Width"] - self.summary_metadata["GridPixelOverlapX"]
                )
                self._tile_height = (
                    self.summary_metadata["Height"] - self.summary_metadata["GridPixelOverlapY"]
                )

            dataset_path = remote_storage_monitor.get_disk_location()
            dataset_path += "" if dataset_path[-1] == os.sep else os.sep
            full_res_path = dataset_path + "Full resolution"
            with self._lock:
                self.res_levels = {
                    0: _ResolutionLevel(
                        remote=True, summary_metadata=self.summary_metadata, path=full_res_path
                    )
                }
            self.axes = {}
            return
        else:
            self._remote_storage_monitor = None

        self.path = dataset_path
        res_dirs = [
            dI for dI in os.listdir(dataset_path) if os.path.isdir(os.path.join(dataset_path, dI))
        ]
        # map from downsample factor to datset
        with self._lock:
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
                with self._lock:
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
                self._read_channel_names()
                print("\rFinished reading channel names", end="")

                # remove axes with no variation
                # single_axes = [axis for axis in self.axes if len(self.axes[axis]) == 1]
                # for axis in single_axes:
                #     del self.axes[axis]

            else:
                with self._lock:
                    self.res_levels[int(np.log2(int(res_dir.split("x")[1])))] = res_level

        # get information about image width and height, assuming that they are consistent for whole dataset
        # (which isn't strictly neccesary)
        with self._lock:
            first_index = list(self.res_levels[0].index.values())[0]
        self._parse_first_index(first_index)

        print("\rDataset opened                ")

    def _read_channel_names(self):
        if self._CHANNEL_AXIS in self.axes.keys():
            self._channel_names = {}
            for key in self.res_levels[0].index.keys():
                axes = {axis: position for axis, position in key}
                if (
                    self._CHANNEL_AXIS in axes.keys()
                    and axes[self._CHANNEL_AXIS] not in self._channel_names.values()
                ):
                    channel_name = self.res_levels[0].read_metadata(axes)["Channel"]
                    self._channel_names[channel_name] = axes[self._CHANNEL_AXIS]
                if len(self._channel_names.values()) == len(self.axes[self._CHANNEL_AXIS]):
                    break

    def _parse_first_index(self, first_index):
        """
        Read through first index to get some global data about images (assuming it is same for all)
        """
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

    def _add_index_entry(self, index_entry):
        """
        Add entry for a image that has been recieved and is now on disk
        """
        with self._lock:
            axes, index_entry = self.res_levels[0].add_index_entry(index_entry)

            # update the axes that have been seen
            for axis_name in axes.keys():
                if axis_name not in self.axes.keys():
                    self.axes[axis_name] = set()
                self.axes[axis_name].add(axes[axis_name])

            # update the map of channel names to channel indices
            self._read_channel_names()

        if not hasattr(self, 'image_width'):
            self._parse_first_index(index_entry)

        return axes

    def _add_storage_monitor_fn(self, callback_fn=None, debug=False):
        """
        Add a callback function that gets called whenever a new image is writtern to disk (for acquisitions in
        progress only)

        Parameters
        ----------
        callback_fn : Callable
            callable with that takes 1 argument, the axes dict of the image just written
        """
        if self._remote_storage_monitor is None:
            raise Exception("Only valid for datasets with writing in progress")

        connected_event = threading.Event()

        push_port = self._remote_storage_monitor.get_port()
        monitor_thread = threading.Thread(
            target=_storage_monitor_fn,
            args=(
                self,
                push_port,
                connected_event,
                callback_fn,
                debug,
            ),
            name="ImageSavedCallbackThread",
        )

        monitor_thread.start()

        # Wait for pulling to start before you signal for pushing to start
        connected_event.wait()  # wait for push/pull sockets to connect

        # start pushing out all the image written events (including ones that have already accumulated)
        self._remote_storage_monitor.start()
        return monitor_thread

    def get_index_keys(self, res_level=0):
        """
        Return a list of every combination of axes that has a image in this dataset
        """
        frozen_set_list = list(self.res_levels[res_level].index.keys())
        # convert to dict
        return [{axis_name: position for axis_name, position in key} for key in frozen_set_list]

    def as_array(self, axes=None, stitched=False, **kwargs):
        """
        Read all data image data as one big Dask array with last two axes as y, x and preceeding axes depending on data.
        The dask array is made up of memory-mapped numpy arrays, so the dataset does not need to be able to fit into RAM.
        If the data doesn't fully fill out the array (e.g. not every z-slice collected at every time point), zeros will
        be added automatically.

        To convert data into a numpy array, call np.asarray() on the returned result. However, doing so will bring the
        data into RAM, so it may be better to do this on only a slice of the array at a time.

        Parameters
        ----------
        axes : list
            list of axes names over which to iterate and merge into a stacked array. If None, all axes will be used.
            The order of axes supplied in this list will be the order of the axes of the returned dask array
        stitched : bool
            If true and tiles were acquired in a grid, lay out adjacent tiles next to one another (Default value = False)
        **kwargs :
            names and integer positions of axes on which to slice data
        Returns
        -------
        dataset : dask array
        """
        if stitched and "GridPixelOverlapX" not in self.summary_metadata:
            raise Exception('This is not a stitchable dataset')
        w = self.image_width if not stitched else self._tile_width
        h = self.image_height if not stitched else self._tile_height
        self._empty_tile = (
            np.zeros((h, w), self.dtype)
            if self.bytes_per_pixel != 3
            else np.zeros((h, w, 3), self.dtype)
        )

        rgb = self.bytes_per_pixel == 3 and self.dtype == np.uint8

        if axes is None:
            axes = self.axes.keys()
        axes_to_slice = kwargs
        axes_to_stack = {key: self.axes[key] for key in axes if key not in kwargs.keys()}
        if stitched:
            if 'row' in axes_to_stack:
                del axes_to_stack['row']
            if 'column' in axes_to_stack:
                del axes_to_stack['column']
            if 'row' in axes_to_slice:
                del axes_to_slice['row']
            if 'column' in axes_to_slice:
                del axes_to_slice['column']

        def read_one_image(block_id, axes_to_stack=axes_to_stack, axes_to_slice=axes_to_slice):
            # a function that reads in one chunk of data
            axes = {key: block_id[i] for i, key in enumerate(axes_to_stack.keys())}
            if stitched:
                # Combine all rows and cols into one stitched image
                self.half_overlap = (self.overlap[0] // 2, self.overlap[1] // 2)
                # get spatial layout of position indices
                row_values = np.array(list(self.axes["row"]))
                column_values = np.array(list(self.axes["column"]))
                # make nested list of rows and columns
                blocks = []
                for row in row_values:
                    blocks.append([])
                    for column in column_values:
                        #remove overlap between tiles
                        if not self.has_image(**axes, **axes_to_slice, row=row, column=column):
                            blocks[-1].append(self._empty_tile)
                        else:
                            tile = self.read_image(**axes, **axes_to_slice, row=row, column=column, memmapped=True)
                            if self.half_overlap[0] != 0:
                                tile = tile[
                                    self.half_overlap[0] : -self.half_overlap[0],
                                    self.half_overlap[1] : -self.half_overlap[1],
                                ]
                            blocks[-1].append(tile)

                if rgb:
                    image = np.concatenate(
                        [
                            np.concatenate(row, axis=len(blocks[0][0].shape) - 2)
                            for row in blocks
                        ],
                        axis=0,
                    )
                else:
                    image = np.array(da.block(blocks))
            else:
                if not self.has_image(**axes, **axes_to_slice):
                    image = self._empty_tile
                else:
                    image = self.read_image(**axes, **axes_to_slice)
            for i in range(len(axes_to_stack.keys())):
                image = image[None]
            return image

        chunks = tuple([(1,) * len(axes_to_stack[axis]) for axis in axes_to_stack.keys()])
        chunks += (w, h)
        if rgb:
            chunks += (3,)

        array = da.map_blocks(
            read_one_image,
            dtype=self.dtype,
            chunks=chunks,
            meta=self._empty_tile
        )

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
        **kwargs :
            names and integer positions of any other axes

        Returns
        -------
        bool :
            indicating whether the dataset has an image matching the specifications
        """
        with self._lock:
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
        with self._lock:
            axes = self._consolidate_axes(
                channel, channel_name, z, position, time, row, col, kwargs
            )

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
        with self._lock:
            axes = self._consolidate_axes(
                channel, channel_name, z, position, time, row, col, kwargs
            )

            res_level = self.res_levels[resolution_level]
            return res_level.read_metadata(axes)

    def close(self):
        with self._lock:
            for res_level in self.res_levels:
                res_level.close()

    def get_channel_names(self):
        with self._lock:
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
