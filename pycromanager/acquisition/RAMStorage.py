# A class for holding data in RAM

from pycromanager.acquisition.acq_eng_py.main.acq_eng_metadata import AcqEngMetadata
import numpy as np
from sortedcontainers import SortedSet
import threading


class RAMDataStorage:
    """
    A class for holding data in RAM
    Implements the methods needed to be a DataSink for AcqEngPy
    """

    def __init__(self):
        self.finished = False
        self.images = {}
        self.image_metadata = {}
        self.axes = {}
        self.finished_event = threading.Event()

    def initialize(self, acq, summary_metadata: dict):
        self.summary_metadata = summary_metadata

    def block_until_finished(self, timeout=None):
        self.finished_event.wait(timeout=timeout)

    def finish(self):
        self.finished = True

    def is_finished(self) -> bool:
        return self.finished

    def put_image(self, tagged_image):
        self.bytes_per_pixel = tagged_image.pix.dtype.itemsize
        self.dtype = tagged_image.pix.dtype
        tags = tagged_image.tags
        axes = AcqEngMetadata.get_axes(tags)
        key = frozenset(axes.items())
        self.images[key] = tagged_image.pix
        self.image_metadata[key] = tags
        for axis in axes.keys():
            if axis not in self.axes:
                self.axes[axis] = SortedSet()
            self.axes[axis].add(axes[axis])
        self._new_image_arrived = True

    def anything_acquired(self) -> bool:
        return self.images != {}

    def has_image(self, channel: int or str, z: int, position: int,
                          time: int, row: int, column: int, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        return key in self.images.keys()

    def read_image(self, channel=None, z=None, time=None, position=None, row=None, column=None, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        if key not in self.index:
            raise Exception("image with keys {} not present in data set".format(key))
        return self.images[key]

    def read_metadata(self, channel=None, z=None, time=None, position=None, row=None, column=None, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        if key not in self.index:
            raise Exception("image with keys {} not present in data set".format(key))
        return self.image_metadata[key]

    def _consolidate_axes(self, channel: int or str, z: int, position: int,
                          time: int, row: int, column: int, **kwargs):
        """
        Pack axes into a convenient format
        """
        axis_positions = {'channel': channel, 'z': z, 'position': position,
                          'time': time, 'row': row, 'column': column, **kwargs}
        # ignore ones that are None
        axis_positions = {n: axis_positions[n] for n in axis_positions.keys() if axis_positions[n] is not None}
        for axis_name in axis_positions.keys():
            # convert any string-valued axes passed as ints into strings
            if self.axes_types[axis_name] == str and type(axis_positions[axis_name]) == int:
                axis_positions[axis_name] = self._string_axes_values[axis_name][axis_positions[axis_name]]

        return axis_positions

    def has_new_image(self):
        """
        For datasets currently being acquired, check whether a new image has arrived since this function
        was last called, so that a viewer displaying the data can be updated.
        """
        # pass through to full resolution, since only this is monitored in current implementation
        if not hasattr(self, '_new_image_arrived'):
            return False # pre-initilization
        new = self._new_image_arrived
        self._new_image_arrived = False
        return new

    def as_array(self, axes=None, **kwargs):
        """
        Read all data image data as one big numpy array with last two axes as y, x and preceeding axes depending on data.
        If the data doesn't fully fill out the array (e.g. not every z-slice collected at every time point), zeros will
        be added automatically.

        This function is modeled of the same one in the NDTiff library, but it uses numpy arrays instead of dask arrays
        because the data is already in RAM

        Parameters
        ----------
        axes : list
            list of axes names over which to iterate and merge into a stacked array. The order of axes supplied in this
            list will be the order of the axes of the returned dask array. If None, all axes will be used in PTCZYX order.

        **kwargs :
            names and integer positions of axes on which to slice data
        """
        if axes is None:
            axes = self.axes.keys()

        empty_image = np.zeros_like(list(self.images.values())[0])
        indices = [np.array(self.axes[axis_name]) for axis_name in list(axes)]
        gridded = np.meshgrid(*indices, indexing='ij')
        result = np.stack(gridded, axis=-1)
        flattened = result.reshape((-1, result.shape[-1]))
        images = []
        for coord in flattened:
            images_key = {key: coord[i] for i, key in enumerate(axes)}
            key = frozenset(images_key.items())
            if key in self.images.keys():
                images.append(self.images[key])
            else:
                images.append(empty_image)
        # reshape to Num axes + image size dimensions
        cube = np.array(images).reshape(tuple(len(i) for i in indices) + empty_image.shape)
        return cube



