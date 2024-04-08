from pyjavaz.wrappers import JavaObject


class JavaRAMDataStorage:
    """
    A python class that wraps a Java-backend RAM data storage.

    This class maintains an index of which images have been saved, but otherwise routes all calls to the Java
    implementation of the RAM data storage.
    """

    def __init__(self, java_RAM_data_storage):
        self._java_RAM_data_storage = java_RAM_data_storage
        self._index_keys = set()

    def _add_index_entry(self, data):
        self._index_keys.add(frozenset(data.items()))

    # def get_channel_names(self):
    #     """
    #     :return: list of channel names (strings)
    #     """
    #     return list(self._channels.keys())

    def get_index_keys(self):
        """
        Return a list of every combination of axes that has a image in this dataset
        """
        frozen_set_list = list(self._index_keys)
        # convert to dict
        return [{axis_name: position for axis_name, position in key} for key in frozen_set_list]

    def is_finished(self) -> bool:
        return self._java_RAM_data_storage.is_finished()

    def has_image(self, channel: int or str, z: int, position: int,
                          time: int, row: int, column: int, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        return key in self._index_keys

    def read_image(self, channel=None, z=None, time=None, position=None, row=None, column=None, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        if key not in self._index_keys:
            return None
        java_hashmap = JavaObject('java.util.HashMap')
        for k, v in axes.items():
            java_hashmap.put(k, v)
        tagged_image = self._java_RAM_data_storage.get_image(java_hashmap)
        pixels = tagged_image.pix
        metadata = tagged_image.tags
        return pixels.reshape(metadata['Height'], metadata['Width'])

    def read_metadata(self, channel=None, z=None, time=None, position=None, row=None, column=None, **kwargs):
        axes = self._consolidate_axes(channel, z, position, time, row, column, **kwargs)
        key = frozenset(axes.items())
        if key not in self._index_keys:
            return None
        java_hashmap = JavaObject('java.util.HashMap')
        for k, v in axes.items():
            java_hashmap.put(k, v)
        tagged_image = self._java_RAM_data_storage.get_image(java_hashmap)
        return tagged_image.tags

    def _consolidate_axes(self, channel: int or str, z: int, position: int,
                          time: int, row: int, column: int, **kwargs):
        """
        Pack axes into a convenient format
        """
        axis_positions = {'channel': channel, 'z': z, 'position': position,
                          'time': time, 'row': row, 'column': column, **kwargs}
        # ignore ones that are None
        axis_positions = {n: axis_positions[n] for n in axis_positions.keys() if axis_positions[n] is not None}
        # for axis_name in axis_positions.keys():
        #     # convert any string-valued axes passed as ints into strings
        #     if self.axes_types[axis_name] == str and type(axis_positions[axis_name]) == int:
        #         axis_positions[axis_name] = self._string_axes_values[axis_name][axis_positions[axis_name]]

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
        raise NotImplementedError("This function is not yet implemented")
        # TODO
        # if axes is None:
        #     axes = self.axes.keys()
        #
        # empty_image = np.zeros_like(list(self.images.values())[0])
        # indices = [np.array(self.axes[axis_name]) for axis_name in list(axes)]
        # gridded = np.meshgrid(*indices, indexing='ij')
        # result = np.stack(gridded, axis=-1)
        # flattened = result.reshape((-1, result.shape[-1]))
        # images = []
        # for coord in flattened:
        #     images_key = {key: coord[i] for i, key in enumerate(axes)}
        #     key = frozenset(images_key.items())
        #     if key in self.images.keys():
        #         images.append(self.images[key])
        #     else:
        #         images.append(empty_image)
        # # reshape to Num axes + image size dimensions
        # cube = np.array(images).reshape(tuple(len(i) for i in indices) + empty_image.shape)
        # return cube



