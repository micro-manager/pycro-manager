from typing import Union, Tuple, Dict, Set, Optional, Any, Sequence
import numpy as np
from typing import Iterable
from abc import ABC, abstractmethod
import weakref

from pydantic import BaseModel
from pydantic import field_validator

from pycromanager.acquisition.new.data_coords import DataCoordinates, DataCoordinatesIterator

from typing import TYPE_CHECKING
if TYPE_CHECKING: # avoid circular imports
    from pycromanager.acquisition.new.acq_future import AcquisitionFuture
    from pycromanager.acquisition.new.data_handler import DataHandler


# def atomic_instruction(cls):
#     cls.atomic_instruction = True
#     return cls

class AcquisitionEvent(BaseModel, ABC):
    num_retries_on_exception: int = 0
    _exception: Exception = None
    _future_weakref: Optional[weakref.ReferenceType['AcquisitionFuture']] = None

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

    def _set_future(self, future: 'AcquisitionFuture'):
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
    _data_handler: "DataHandler" = None # executor will provide this at runtime
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



