import threading
import queue
from typing import Any, Dict, Tuple, Callable, Union, Sequence, Optional
import numpy as np

from pycromanager.acquisition.new.data_coords import DataCoordinates
from pycromanager.acquisition.new.apis.data_storage import DataStorageAPI
from pydantic.types import JsonValue
from dataclasses import dataclass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pycromanager.acquisition.new.acq_future import AcquisitionFuture


class _PeekableQueue(queue.Queue):
    def peek(self):
        with self.mutex:
            while not self._qsize():
                self.not_empty.wait()
            return self.queue[0]

# make a dataclass to hold the data, metadata, future, and boolean flag for whether the data has been processed
@dataclass
class _DataMetadataFutureHolder:
    data: np.ndarray
    metadata: Dict
    future: Optional["AcquisitionFuture"]
    processed: bool = False

    def upack(self):
        return self.data, self.metadata, self.future

class DataHandler:
    """
    Object that handles acquired data while it is waiting to be saved. This object is thread safe and manages
    the handoff of images while they are waiting to be saved, providing temporary access to it along the way.

    This class manages one or two queues/threads, depending on whether a processing function is provided. If a
    processing function is provided, the data will be processed in a separate thread before being passed to the data
    storage object. If no processing function is provided, the data will be passed directly to the data storage object.
    """

    # This class must create at least one additional thread (the saving thread)
    # and may create another for processing data

    def __init__(self, storage: DataStorageAPI,
                 process_function: Callable[[DataCoordinates, np.ndarray, JsonValue],
                                Optional[Union[DataCoordinates, np.ndarray, JsonValue,
                                               Tuple[DataCoordinates, np.ndarray, JsonValue]]]] = None):
        self._storage = storage
        self._process_function = process_function
        self._intake_queue = _PeekableQueue()
        # locks for synchronizing access the queues/dicts
        self._data_metadata_future_tuple: Dict[Any, _DataMetadataFutureHolder] = {}
        self._intake_thread = threading.Thread(target=self._run_intake_thread)
        self._intake_thread.start()
        if process_function:
            self._processed_lock = threading.Lock()
            self._processed_queue = _PeekableQueue()
            self._storage_thread = threading.Thread(target=self._run_storage_thread)
            self._storage_thread.start()
        else:
            self._processed_queue = None
            self._storage_thread = None

    @staticmethod
    def _unpack_processed_image(processed):
        """ Convert coordinates dict to DataCoordinates object if necessary """
        coordinates, data, metadata = processed
        if isinstance(coordinates, dict):
            coordinates = DataCoordinates(coordinates)
        return coordinates, data, metadata

    def _run_intake_thread(self):
        while True:
            if self._process_function:
                # don't remove it until it has been processed
                coordinates = self._intake_queue.peek()
                print('peek success')
                # shutdown condition
                if coordinates is None:
                    self._intake_queue.get()
                    # TODO: it would be nice to give a signal to the image processor to shut down
                    #  probably could do this by adding a new protocol that can be checked
                    #  to allow backwards compatibility
                    self._processed_queue.put(None)  # propagate the shutdown signal
                    break

                data, metadata, future = self._data_metadata_future_tuple[coordinates].upack()
                processed = self._process_function(coordinates, data, metadata)

                original_coordinates = coordinates
                original_data_coordinates_replaced = False
                # deal with the fact that the processor may return no items, a single item, or a list of items
                if processed is None:
                    pass # the data was discarded or diverted
                    # Could add callback here to notify the future that the data was discarded
                elif isinstance(processed, tuple) and not isinstance(processed[0], tuple):  # single item
                    coordinates, data, metadata = self._unpack_processed_image(processed)
                    if coordinates == original_coordinates:
                        original_data_coordinates_replaced = True
                    self._processed_queue.put(coordinates)
                    self._data_metadata_future_tuple[coordinates] = _DataMetadataFutureHolder(
                        data, metadata, future, processed=True)
                    if future:
                        future._notify_data(coordinates, data, metadata, processed=True, stored=False)
                else:  # multiple items
                    for item in processed:
                        coordinates, data, metadata = self._unpack_processed_image(item)
                        if coordinates == original_coordinates:
                            original_data_coordinates_replaced = True
                        self._processed_queue.put(coordinates)
                        self._data_metadata_future_tuple[coordinates] = _DataMetadataFutureHolder(
                            data, metadata, future, processed=True)
                        if future:
                            future._notify_data(coordinates, data, metadata, processed=True, stored=False)
                if not original_data_coordinates_replaced:
                    # if the image processor did not provide a new image with the same coordinates, discard the original
                    self._data_metadata_future_tuple.pop(original_coordinates)
                # remove the item from the intake queue
                self._intake_queue.get()
            else:
                # transfer to storage thread
                shutdown = self._transfer_to_storage()
                if shutdown:
                    break

    def _run_storage_thread(self):
        """ if an image processor is active, this additional thread will take its processed images and save them """
        while True:
            shutdown = self._transfer_to_storage()
            if shutdown:
                break
    def _transfer_to_storage(self):
        """
        Take items from the source queue and put them into the storage queue. If there is a processing function,
        the source queue is the output queue of the processing function. If there is no processing function, the source
        queue is the intake queue.
        """

        coordinates = self._processed_queue.peek() if self._process_function else self._intake_queue.peek()
        if coordinates is None:
            # shutdown condition
            self._processed_queue.get() if self._process_function else self._intake_queue.get() # remove it
            self._storage.finish()
            return True
        else:
            data, metadata, future = self._data_metadata_future_tuple[coordinates].upack()
            self._storage.put(coordinates, data, metadata) # once this returns the storage is responsible for the data
            coordinates = self._processed_queue.get() if self._process_function else self._intake_queue.get()
            self._data_metadata_future_tuple.pop(coordinates)
            if future:
                future._notify_data(coordinates, data, metadata, processed=True, stored=True)
            return False

    def join(self):
        """
        Wait for the threads to finish
        """
        self._intake_thread.join()
        if self._storage_thread:
            self._storage_thread.join()

    def get(self, coordinates: DataCoordinates, return_data=True, return_metadata=True, processed=None,
            ) -> Optional[Tuple[np.ndarray, JsonValue]]:
        """
        Get an image and associated metadata. If they are present, either in the intake queue or the storage queue
        (if it exists), return them. If not present, get them from the storage object. If not present there, return None
        """
        data_metadata_future = self._data_metadata_future_tuple.get(coordinates, None)
        if processed is not None:
            if processed and data_metadata_future and not data_metadata_future.processed:
                # the data is not yet processed, so return None
                return None
        data, metadata = None, None
        if data_metadata_future:
            data, metadata, future = data_metadata_future.upack()
        else:
            # its not currently managed by the data handler, so check the storage object
            # don't do both if you dont have to because this may be from disk
            if return_data:
                data = self._storage.get_data(coordinates)
                if data is None:
                    raise KeyError(f"Image with coordinates {coordinates} not found")
            if return_metadata:
                metadata = self._storage.get_metadata(coordinates)
                if metadata is None:
                    raise KeyError(f"Metadata with coordinates {coordinates} not found")
        return data, metadata


    def put(self, coordinates: Any, image: np.ndarray, metadata: Dict, acquisition_future: Optional["AcquisitionFuture"]):
        """
        Hand off this image to the data handler. It will handle handoff to the storage object and image processing
        if requested, as well as providing temporary access to the image and metadata as it passes throught this
        pipeline. If an acquisition future is provided, it will be notified when the image arrives, is processed, and
        is stored.
        """
        # store the data before adding a record of it to the queue, to avoid having to lock anything
        self._data_metadata_future_tuple[coordinates] = _DataMetadataFutureHolder(
            image, metadata, acquisition_future)
        self._intake_queue.put(coordinates)

        if acquisition_future:
            acquisition_future._notify_data(coordinates, image, metadata, processed=False, stored=False)

    def finish(self):
        """
        Signal to the data handler that no more data will be added. This will cause all threads to initiate shutdown
        and call the finish() method of the storage object.
        """
        self._intake_queue.put(None)