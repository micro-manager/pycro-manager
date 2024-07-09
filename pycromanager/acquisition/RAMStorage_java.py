from pyjavaz.wrappers import JavaObject
from ndstorage.ndstorage_base import NDStorageBase

class NDRAMDatasetJava(NDStorageBase):
    """
    A python class that wraps a Java-backend RAM data storage.

    This class maintains an index of which images have been saved, but otherwise routes all calls to the Java
    implementation of the RAM data storage.
    """

    def __init__(self, java_RAM_data_storage):
        super().__init__()
        self._java_RAM_data_storage = java_RAM_data_storage
        self._index_keys = set()

    def __del__(self):
        self.close()

    def close(self):
        self._java_RAM_data_storage = None # allow the Java side to be garbage collected

    def add_available_axes(self, image_coordinates):
        """
        The Java RAM storage has received a new image with the given axes. Add these axes to the index.
        """
        self._index_keys.add(frozenset(image_coordinates.items()))
        # update information about the available images
        self._update_axes(image_coordinates)
        self._new_image_event.set()
        if self.dtype is None:
            image = self.read_image(**image_coordinates)
            self._infer_image_properties(image)

    def get_image_coordinates_list(self):
        """
        Return a list of every combination of axes that has an image in this dataset
        """
        frozen_set_list = list(self._index_keys)
        # convert to dict
        return [{axis_name: position for axis_name, position in key} for key in frozen_set_list]

    def is_finished(self) -> bool:
        return self._java_RAM_data_storage.is_finished()

    def has_image(self, channel=None, z=None, time=None, position=None, row=None, column=None, **kwargs):
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


