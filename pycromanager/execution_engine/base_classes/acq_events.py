from typing import Union, Tuple, Dict, Set, Optional, Any, Sequence
import numpy as np
from typing import Iterable
from abc import ABC, abstractmethod
import weakref

from pydantic import BaseModel
from pydantic import field_validator, Field

from pycromanager.execution_engine.data_coords import DataCoordinates, DataCoordinatesIterator
from pycromanager.execution_engine.data_handler import DataHandler

from typing import TYPE_CHECKING
if TYPE_CHECKING: # avoid circular imports
    from pycromanager.execution_engine.acq_future import AcquisitionFuture

class AcquisitionEvent(BaseModel, ABC):
    num_retries_on_exception: int = 0
    _future_weakref: Optional[weakref.ReferenceType['AcquisitionFuture']] = None
    _finished: bool = False

    # TODO: want to make this specific to certain attributes?
    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def execute(self) -> Any:
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

    def _post_execution(self, return_value: Optional[Any] = None, exception: Optional[Exception] = None,
                        stopped=False, aborted=False):
        """
        Method that is called after the event is executed to update acquisition futures about the event's status.
        This is called automatically by the Executor and should not be overriden by subclasses.

        Args:
            return_value: Return value of the event
            exception: Exception that was raised during execution, if any
            stopped: Whether the event was stopped
            aborted: Whether the event was aborted
        """
        if self._future_weakref is None:
            raise Exception("Future not set for event")
        future = self._future_weakref()
        if future is not None:
            future._notify_execution_complete(return_value, exception)
        self._finished = True

    def is_finished(self):
        return self._finished

class Stoppable:
    # TODO: this should be on the future, if youre not going to merge them into one
    #  becuase the event can be reused
    """
    Acquistition events that can be stopped should inherit from this class. They are responsible for checking if
    is_stop_requested() returns True and stopping their execution if it does. When stopping, an orderly shutdown
    should be performed, unlike when aborting, which should be immediate. The details of what such an orderly
    shutdown entails are up to the implementation of the event.
    """
    _stop_requested: bool = False

    def _stop(self):
        """
        This is called by the acquisitionFuture object
        """
        self._stop_requested = True

    def is_stop_requested(self):
        return self._stop_requested

class Abortable:
    """
    Acquisition events that can be aborted should inherit from this class. They are responsible for checking if
    is_abort_requested() returns True and aborting their execution if it does. When aborting, the event should
    immediately stop its executiond.
    """
    _abort_requested: bool = False

    def _abort(self):
        """
        This is handled by the Future
        """
        self._abort_requested = True

    def is_abort_requested(self):
        return self._abort_requested

class DataProducing(BaseModel):
    """
    Acquisition events that produce data should inherit from this class. They are responsible for putting data
    into the output queue. This class provides a method for putting data into the output queue. It must be passed
    a DataHandler object that will handle the data, and an image_coordinate_iterator object that generates the
    coordinates of each piece of data (i.e. image) that will be produced by the event. For example, {time: 0},
    {time: 1}, {time: 2} for a time series acquisition.
    """
    data_handler: DataHandler = None
    # This is eventually an ImageCoordinatesIterator. If an Iterable[ImageCoordinates] or
    # Iterable[Dict[str, Union[int, str]]] is provided, it will be auto-converted to an ImageCoordinatesIterator
    image_coordinate_iterator: Union[DataCoordinatesIterator,
                                     Iterable[DataCoordinates],
                                     Iterable[Dict[str, Union[int, str]]]]

    # TODO: is there any point to pydantic if I'm just telling it to ignore stuff anyway?
    class Config:
        arbitrary_types_allowed = True

    @field_validator('image_coordinate_iterator', mode='before')
    def _convert_to_image_coordinates_iterator(cls, v):
        return DataCoordinatesIterator.create(v)

    def put_data(self, data_coordinates: DataCoordinates, image: np.ndarray, metadata: Dict):
        """
        Put data into the output queue
        """
        self.data_handler.put(data_coordinates, image, metadata, self._future_weakref())



