"""
Adapters for NDTiff and NDRam storage_implementations classes
"""
from typing import Union, Dict
from pycromanager.execution_engine.kernel.data_storage_api import DataStorageAPI
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from ndstorage import NDRAMDataset, NDTiffDataset
import numpy as np
from pydantic.types import JsonValue

class _NDRAMOrTiffStorage(DataStorageAPI):
    """
    Wrapper class for NDTiffDataset and NDRAMDataset to implement the DataStorageAPI protocol
    """

    _storage: Union[NDTiffDataset, NDRAMDataset]

    def __contains__(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> bool:
        """Check if item is in the container."""
        return self._storage.has_image(**DataCoordinates(data_coordinates))

    def __getitem__(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> np.ndarray:
        """ Read a single data corresponding to the given coordinates. Same as get_data() """
        return self.get_data(DataCoordinates(data_coordinates))

    def get_data(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> np.ndarray:
        """
        Read a single data corresponding to the given coordinates
        """
        return self._storage.read_image(**DataCoordinates(data_coordinates))

    def get_metadata(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> JsonValue:
        """
        Read metadata corresponding to the given coordinates
        """
        return self._storage.read_metadata(**DataCoordinates(data_coordinates))

    def put(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]], data: np.ndarray,
            metadata: JsonValue):
        """
        Add data and corresponding metadata to the dataset. Once this method has been called, the data and metadata
        should be immediately available to be read by get_data and get_metadata. For disk-backed storage_implementations, this may
        require temporarily caching the data in memory until it can be written to disk.

        Parameters
        ----------
        data_coordinates : DataCoordinates or dict
            Coordinates of the data
        data : np.ndarray
            Data to be stored
        metadata : dict
            Metadata associated with the data
        """
        self._storage.put_image(DataCoordinates(data_coordinates), data, metadata)

    def finish(self):
        """
        No more data will be added to the dataset. This method should be called after the last call to put()
        and makes the dataset read-only.
        """
        self._storage.finish()

    def close(self):
        """
        Close the dataset, releasing any resources it holds. No more images will be added or requested
        """
        self._storage.close()


class NDTiffStorage(_NDRAMOrTiffStorage):
    """
    Adapter for NDTiffDataset to implement the DataStorageAPI protocol
    """
    def __init__(self, directory: str, name: str = None, summary_metadata: JsonValue = None):
        self._storage = NDTiffDataset(dataset_path=directory, name=name, writable=True)
        if summary_metadata is None:
            summary_metadata = {}
        self._storage.initialize(summary_metadata)

class NDRAMStorage(_NDRAMOrTiffStorage):
    """
    Adapter for NDRAMDataset to implement the DataStorageAPI protocol
    """
    def __init__(self, summary_metadata: JsonValue = None):
        self._storage = NDRAMDataset()
        if summary_metadata is None:
            summary_metadata = {}
        self._storage.initialize(summary_metadata)