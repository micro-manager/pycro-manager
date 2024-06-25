from typing import Union, List, Tuple, Callable, Dict, Set, Optional, Any, Sequence
import numpy as np
from queue import Queue
from typing import Iterable
from abc import ABC, abstractmethod
import threading
import weakref
import warnings

from pycromanager.acquisition.new.data_coords import DataCoordinates, DataCoordinatesIterator
from pycromanager.acquisition.new.data_storage import DataStorageAPI
from pycromanager.acquisition.new.data_handler import DataHandler

from pydantic import BaseModel
from pydantic import field_validator


# def atomic_instruction(cls):
#     cls.atomic_instruction = True
#     return cls


class AcquisitionFuture:

    def __init__(self, event: Union['AcquisitionEvent', 'DataProducingAcquisitionEvent'], data_handler: DataHandler):
        self._event = event
        event._set_future(self) # so that the event can notify the future when it is done and when data is acquired
        self._data_handler = data_handler
        self._event_complete_condition = threading.Condition()
        self._data_notification_condition = threading.Condition()
        self._event_complete = False
        self._acquired_data_coordinates: Set[DataCoordinates] = set()
        self._processed_data_coordinates: Set[DataCoordinates] = set()
        self._saved_data_coordinates: Set[DataCoordinates] = set()
        self._awaited_acquired_data: Dict[DataCoordinates, Tuple[Any, Any]] = {}
        self._awaited_processed_data: Dict[DataCoordinates, Tuple[Any, Any]] = {}
        self._awaited_saved_data: Dict[DataCoordinates, Tuple[Any, Any]] = {}

    def _notify_execution_complete(self, exception: Exception):
        """
        Notify the future that the event has completed
        """
        with self._event_complete_condition:
            self._event_complete = True
            self._event_complete_condition.notify_all()

    def await_execution(self):
        """
        Block until the event is complete
        """
        with self._event_complete_condition:
            while not self._event_complete:
                self._event_complete_condition.wait()

    def _notify_data(self, image_coordinates: DataCoordinates, data, metadata, processed=False, saved=False):
        """
        Notify the future that data has been acquired by a data producing event. This does not mean
        the event is done executing. It also does not mean the data has been stored yet. It is simply
        in an output queue waiting to be gotten by the image storage/image/processing thread

        Args:
            image_coordinates: The coordinates of the acquired data
            data: The data itself
            metadata: Metadata associated with the data
            processed: Whether the data has been processed
            saved: Whether the data has been saved
        """
        with self._data_notification_condition:
            # pass the data to the function that is waiting on it
            if not processed and not saved:
                self._acquired_data_coordinates.add(image_coordinates)
                if image_coordinates in self._awaited_acquired_data:
                    self._awaited_acquired_data[
                        image_coordinates] = (data if self._awaited_acquired_data[image_coordinates][0] else None,
                                              metadata if self._awaited_acquired_data[image_coordinates][1] else None)
            elif processed and not saved:
                self._processed_data_coordinates.add(image_coordinates)
                if image_coordinates in self._awaited_processed_data:
                    self._awaited_processed_data[
                        image_coordinates] = (data if self._awaited_processed_data[image_coordinates][0] else None,
                                              metadata if self._awaited_processed_data[image_coordinates][1] else None)
            elif processed and saved:
                self._saved_data_coordinates.add(image_coordinates)
                if image_coordinates in self._awaited_saved_data:
                    self._awaited_saved_data[
                        image_coordinates] = (data if self._awaited_saved_data[image_coordinates][0] else None,
                                              metadata if self._awaited_saved_data[image_coordinates][1] else None)
            else:
                raise ValueError("Invalid arguments")
            self._data_notification_condition.notify_all()

    def _check_if_coordinates_possible(self, coordinates):
        """
        Check if the given coordinates are possible for this event. raise a ValueError if not
        """
        possible = self._event.image_coordinate_iterator.might_produce_coordinates(coordinates)
        if possible is False:
            raise ValueError("This event is not expected to produce the given coordinates")
        elif possible is None:
            # TODO: suggest a better way to do this (ie a smart generator that knows if produced coordinates are valid)
            warnings.warn("This event may not produce the given coordinates")


    # TODO: write tests for this with returning data, metadata, and both, and neither
    #  Also try adding in a big delay in the queue or image saving and make sure it still works
    def await_data(self, coordinates: Optional[Union[DataCoordinates, Dict[str, Union[int, str]],
                                               DataCoordinatesIterator, Sequence[DataCoordinates],
                                               Sequence[Dict[str, Union[int, str]]]]],
                   return_data: bool = False, return_metadata: bool = False,
                   data_processed: bool = False, data_stored: bool = False):
        """
        Block until the event's data is acquired/processed/saved, and optionally return the data/metadata.
        when waiting for the data to be acquired (i.e. before it is processed), since there is no way to guarantee that
        this function is called before the data is acquired, the data may have already been saved and not readily
        available in RAM. In this case, the data will be read from disk.

        Args:
            coordinates: A single DataCoordinates object/dictionary, or Sequence (i.e. list or tuple) of DataCoordinates
             objects/dictionaries. If None, this function will block until the next data is acquired/processed/saved
            return_data: whether to return the data
            return_metadata: whether to return the metadata
            data_processed: whether to wait until data has been processed. If not data processor is in use,
                then this parameter has no effect
            data_stored: whether to wait for data that has been saved
        """
        # Check if this event produces data
        if not isinstance(self._event, DataProducingAcquisitionEvent):
            raise ValueError("This event does not produce data")

        coordinates_iterator = DataCoordinatesIterator.create(coordinates)
        # check that an infinite number of images is not requested
        if not coordinates_iterator.is_finite():
            raise ValueError("Cannot wait for an infinite number of images")

        # Iterate through all of the requested images, if they haven't yet been acquired/processed/saved, register them
        # in awaited_data so that they'll be hung onto if they arrive while this method is running. This may avoid
        # having to retrieve them from disk later
        result = {}
        to_read = set()
        with self._data_notification_condition:
            # lock to avoid inconsistencies with the data that is being awaited
            for data_coordinates in coordinates_iterator:
                if not data_processed and not data_stored:
                    # make sure this is a valid thing to wait for. This can only be done before processing and
                    #  storage, because processors and data storage classes may optionally modify the data
                    self._check_if_coordinates_possible(coordinates)
                    if data_coordinates not in self._acquired_data_coordinates:
                        # register that we're awaiting this data, so that if it arrives on the other thread while other
                        # images are being read from disk, it will be hung onto in memory, thereby avoid unnecessary reads
                        self._awaited_acquired_data[coordinates] = (return_data, return_metadata)
                    else:
                        to_read.add(data_coordinates)
                elif data_processed and not data_stored:
                    if data_coordinates not in self._processed_data_coordinates:
                        self._awaited_processed_data[coordinates] = (return_data, return_metadata)
                    else:
                        to_read.add(data_coordinates)
                else: # data stored
                    if data_coordinates not in self._saved_data_coordinates:
                        self._awaited_saved_data[coordinates] = (return_data, return_metadata)
                    else:
                        to_read.add(data_coordinates)

        # retrieve any data that has already passed through the pipeline from the data storage, via the data handler
        for data_coordinates in to_read:
            data, metadata = self._data_handler.get(data_coordinates, return_data, return_metadata)
            # save memory for a potential big retrieval
            result[data_coordinates] = (data if return_data else None, metadata if return_metadata else None)

        # now that we've gotten all the data from storage that was missed before this method was called,
        #  proceed to getting all the data was awaited on another thread
        with self._data_notification_condition:
            # order doesn't matter here because we're just grabbing it all from RAM
            if not data_processed and not data_stored:
                for data_coordinates in self._awaited_acquired_data.keys():
                    data = return_data
                    while data is True or data is False: # once the data is no longer a boolean, it's the actual data
                        self._data_notification_condition.wait()
                        data, metadata = self._awaited_acquired_data[data_coordinates]
                    # remove from temporary storage and put into result
                    result[data_coordinates] = self._awaited_acquired_data.pop(data_coordinates)

                # Same thing for other steps in the pipeline
                for data_coordinates in self._awaited_processed_data.keys():
                    data = return_data
                    while data is True or data is False:
                        self._data_notification_condition.wait()
                        data, metadata = self._awaited_processed_data[data_coordinates]
                    result[data_coordinates] = self._awaited_processed_data.pop(data_coordinates)

                for data_coordinates in self._awaited_saved_data.keys():
                    data = return_data
                    while data is True or data is False:
                        self._data_notification_condition.wait()
                        data, metadata = self._awaited_saved_data[data_coordinates]
                    result[data_coordinates] = self._awaited_saved_data.pop(data_coordinates)

        # Now package the result up
        all_data, all_metadata = zip(*result.values())
        # if the original coordinates were not a sequence, don't return a sequence
        if not isinstance(coordinates, dict) or not isinstance(coordinates, DataCoordinates):
            all_data = all_data[0]
            all_metadata = all_metadata[0]
        if return_data and return_metadata:
            return all_data, all_metadata
        elif return_data:
            return all_data
        elif return_metadata:
            return all_metadata


class AcquisitionEvent(BaseModel, ABC):
    num_retries_on_exception: int = 0
    _exception: Exception = None
    _future_weakref: Optional[weakref.ReferenceType[AcquisitionFuture]] = None

    # TODO: want to make this specific to certain attributes
    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def execute(self):
        """
        Execute the event. This event is called by the executor, and should be overriden by subclasses to implement
        the event's functionality
        """
        pass

    def _set_future(self, future: AcquisitionFuture):
        """
        Called by the executor to set the future associated with this event
        """
        # Store this as a weakref so that if user code does not hold a reference to the future,
        # it can be garbage collected. The event should not give access to the future to user code
        self._future_weakref = weakref.ref(future)

    def _post_execution(self):
        """
        Method that is called after the event is executed to update acquisition futures about the event's status.
        This is called automatically by the Executor and should not be overriden by subclasses.

        Args:
            future (AcquisitionFuture): The future associated with this event
        """
        if self._future_weakref is None:
            raise ValueError("Event has not been executed yet")
        future = self._future_weakref()
        if future is not None:
            future._notify_execution_complete(self._exception)



class DataProducingAcquisitionEvent(AcquisitionEvent):
    """
    Special type of acquisition event that produces data. It must be passed an image_coordinate_iterator
    object that generates the coordinates of each piece of data (i.e. image) that will be produced by the event.
    For example, {time: 0}, {time: 1}, {time: 2} for a time series acquisition.
    """
    _data_handler: DataHandler = None # executor will provide this at runtime
    # This is eventually an ImageCoordinatesIterator. If an Iterable[ImageCoordinates] or
    # Iterable[Dict[str, Union[int, str]]] is provided, it will be auto-converted to an ImageCoordinatesIterator
    image_coordinate_iterator: Union[DataCoordinatesIterator,
                                     Iterable[DataCoordinates],
                                     Iterable[Dict[str, Union[int, str]]]]

    @field_validator('image_coordinate_iterator', mode='before')
    def _convert_to_image_coordinates_iterator(cls, v):
        return DataCoordinatesIterator.create(v)

    def put_data(self, data_coordinates: DataCoordinates, image: np.ndarray, metadata: Dict):
        """
        Put data into the output queue
        """
        self._data_handler.put(data_coordinates, image, metadata, self._future_weakref())



