from typing import Union, List, Tuple, Callable, Dict
from pydantic import BaseModel
import numpy as np
from typing_extensions import Protocol, runtime_checkable
from queue import Queue
from typing import Iterable
import itertools
from abc import ABC, abstractmethod
import threading

from pycromanager.acquisition.new.devices import Camera


from pycromanager.acquisition.new.image_coords import ImageCoordinates



from pydantic import BaseModel
import uuid


# def atomic_instruction(cls):
#     cls.atomic_instruction = True
#     return cls
#
# @atomic_instruction
# class DeviceInstruction(BaseModel):
#     """
#     Represents an instruction to a device. i.e.
#     """
#     device_action: Callable # bound method of a device
#     # TODO: enforce that arguments must be primitives or arrays?
#     args: Tuple
#
#     def execute(self):
#         """
#         Execute the device instruction
#         """
#         return self.device_action(*self.args)

# @atomic_instruction


class AcquisitionFuture(BaseModel):
    event: 'AcquisitionEvent'
    _event_complete_condition: threading.Condition = threading.Condition()
    _event_complete: bool = False

    def notify_done(self, exception: Exception):
        """
        Notify the future that the event has completed
        """
        with self._event_complete_condition:
            self._event_complete = True
            self._event_complete_condition.notify_all()

    def notify_data_acquired(self, image_coordinates: ImageCoordinates):
        """
        Notify the future that data has been acquired by a data producing event. This does not mean
        the event is done executing
        """
        # TODO: could have the notifier grab the data from RAM if available, otherwise read it from disk
        pass

    def await_execution(self):
        """
        Block until the event is complete
        """
        with self._event_complete_condition:
            while not self._event_complete:
                self._event_complete_condition.wait()

    def await_data_acquired(self):
        """
        Block until data is acquired by the event, and optionally return
        If the data was already acquired, read it from the dataset
        """
        pass



class DataOutputQueue:
    """
    Output queue for data (i.e. images) captured by an AcquisitionEvent
    """
    _queue: Queue = Queue()

    def put(self, future: 'AcquisitionFuture',  coordinates: ImageCoordinates, image: np.ndarray, metadata: Dict):
        """
        Put an image and associated metadata into the queue
        """
        self._queue.put((coordinates, image, metadata))
        future.notify_data_acquired(coordinates)

    def get(self):
        """
        Get an image and associated metadata from the queue
        """
        return self._queue.get()


class AcquisitionEvent(BaseModel, ABC):
    num_retries_on_exception: int = 0
    _exception: Exception = None
    _future: AcquisitionFuture = None

    # TODO: want to make this specifc to certain attributes
    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def execute(self):
        """
        Execute the event. This event is called by the executor, and should be overriden by subclasses to implement
        the event's functionality
        """
        pass

    def _post_execution(self):
        """
        Method that is called after the event is executed to update acquisition futures about the event's status.
        This is called automatically by the Executor and should not be overriden by subclasses.

        Args:
            future (AcquisitionFuture): The future associated with this event
        """
        if self._future is None:
            raise ValueError("Event has not been executed yet")
        # notify the future that the event has completed
        self._future.notify_done(self._exception)



class DataProducingAcquisitionEvent(AcquisitionEvent):
    """
    Special type of acquisition event that produces data
    """
    data_output_queue: DataOutputQueue = None # executor will provide this at runtime
    image_coordinate_iterator: Iterable[ImageCoordinates]

    def put_data(self, image_coordinates: ImageCoordinates, image: np.ndarray, metadata: Dict):
        """
        Put data into the output queue
        """
        self.data_output_queue.put(self._future, image_coordinates, image, metadata)



class ReadoutImages(DataProducingAcquisitionEvent):
    """
    Readout one or more images (and associated metadata) from a camera

    Attributes:
        num_images (int): The number of images to read out.
        camera (Camera): The camera object to read images from.
        image_coordinate_iterator (Iterable[ImageCoordinates]): An iterator or list of ImageCoordinates objects, which
            specify the coordinates of the images that will be read out, should be able to provide at least num_images
            elements.
    """
    num_images: int
    camera: Camera

    def execute(self):
        image_counter = itertools.count() if self.num_images is None else range(self.num_images)
        for image_number, image_coordinates in zip(image_counter, self.image_coordinate_iterator):
            while True:
                # TODO: read from state to check for cancel condition
                #  this can be made more efficient in the future with a new image buffer that provides callbacks
                # on a new image recieved so that polling can be avoided
                image, metadata = self.camera.pop_image(timeout=0.01) # only block for 10 ms so stop event can be checked
                if image is not None:
                    self.put_data(image_coordinates, image, metadata)
                    break


class StartCapture(AcquisitionEvent):
    """
    Special device instruction that captures images from a camera
    """
    num_images: int
    camera: Camera

    def execute(self):
        """
        Capture images from the camera
        """
        try:
            self.camera.arm(self.num_images)
            self.camera.start()
        except Exception as e:
            self.camera.stop()
            raise e

