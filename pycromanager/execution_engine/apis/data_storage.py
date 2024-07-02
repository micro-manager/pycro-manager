"""
Protocol for storage class that acquisitions ultimate write to where the acquisition data ultimately gets stored
"""

from typing import Protocol, runtime_checkable, Union, List, Tuple, Dict, Any
from pycromanager.execution_engine.data_coords import DataCoordinates
import numpy as np
from pydantic.types import JsonValue

@runtime_checkable
class DataStorageAPI(Protocol):

    # TODO: about these type hints: better to use the dicts only or also include the DataCoordinates?
    #  DataCoordinates can essentially be used as a dict anyway due to duck typing, so
    #  maybe its better that other implementations not have to depend on the DataCoordinates class
    def __contains__(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> bool:
        """Check if item is in the container."""
        ...

    def get_data(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> np.ndarray:
        """
        Read a single data corresponding to the given coordinates
        """
        ...

    def get_metadata(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]]) -> JsonValue:
        """
        Read metadata corresponding to the given coordinates
        """
        ...

    # TODO: one alternative to saying you have to make the data immediately available is to have a callback
    #  that is called when the data is available. This would allow for disk-backed storage to write the data
    #  to disk before calling the callback.
    def put(self, data_coordinates: Union[DataCoordinates, Dict[str, Union[int, str]]], data: np.ndarray,
            metadata: JsonValue):
        """
        Add data and corresponding metadata to the dataset. Once this method has been called, the data and metadata
        should be immediately available to be read by get_data and get_metadata. For disk-backed storage, this may
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
        ...

    def finish(self):
        """
        No more data will be added to the dataset. This method should be called after the last call to put()
        and makes the dataset read-only.
        """
        ...

    def close(self):
        """
        Close the dataset, releasing any resources it holds. No more images will be added or requested
        """
        ...

    #### Other methods copied from the NDStorage API that possibly could be useful to include in the future ####

    # @abstractmethod
    # def initialize(self, summary_metadata: dict):
    #     """
    #     Initialize the dataset with summary metadata
    #     """
    # TODO: if implementation, may want to change this global metadata
    #     pass

#     @abstractmethod
#     def get_image_coordinates_list(self) -> List[Dict[str, Union[int, str]]]:
#         """
#         Return a list of the coordinates (e.g. {'channel': 'DAPI', 'z': 0, 'time': 0}) of every image in the dataset
#
#         Returns
#         -------
#         list
#             List of image coordinates
#         """
#         pass
#
#     @abstractmethod
#     def await_new_image(self, timeout=None):
#         """
#         Wait for a execution_engine image to arrive in the dataset
#
#         Parameters
#         ----------
#         timeout : float, optional
#             Maximum time to wait in seconds (Default value = None)
#
#         Returns
#         -------
#         bool
#             True if a execution_engine image has arrived, False if the timeout was reached
#         """
#         pass
#
#     @abstractmethod
#     def is_finished(self) -> bool:
#         """
#         Check if the dataset is finished and no more images will be added
#         """
#         pass
#
#
#
#     @abstractmethod
#     def as_array(self, axes: List[str] = None, stitched: bool = False,
#                  **kwargs: Union[int, str]) -> 'dask.array':
#         """
#         Create one big Dask array with last two axes as y, x and preceding axes depending on data.
#         If the dataset is saved to disk, the dask array is made up of memory-mapped numpy arrays,
#         so the dataset does not need to be able to fit into RAM.
#         If the data doesn't fully fill out the array (e.g. not every z-slice collected at every time point),
#         zeros will be added automatically.
#
#         To convert data into a numpy array, call np.asarray() on the returned result. However, doing so will bring the
#         data into RAM, so it may be better to do this on only a slice of the array at a time.
#
#         Parameters
#         ----------
#         axes : list, optional
#             List of axes names over which to iterate and merge into a stacked array.
#             If None, all axes will be used in PTCZYX order (Default value = None).
#         stitched : bool, optional
#             If True and tiles were acquired in a grid, lay out adjacent tiles next to one another
#             (Default value = False)
#         **kwargs :
#             Names and integer positions of axes on which to slice data
#
#         Returns
#         -------
#         dataset : dask array
#             Dask array representing the dataset
#         """
#         pass
#
# class WritableNDStorageAPI(NDStorageAPI):
#     """
#     API for NDStorage classes to which images can be written
#     """
#

#
#     @abstractmethod
#     def block_until_finished(self, timeout=None):
#         """
#         Block until the dataset is finished and all images have been written
#
#         Parameters
#         ----------
#         timeout : float, optional
#             Maximum time to wait in seconds (Default value = None)
#
#         Returns
#         -------
#         bool
#             True if the dataset is finished, False if the timeout was reached
#         """
#         pass
