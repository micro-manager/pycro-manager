""""
Base classes for device_implementations that can be used by the execution engine
"""

from abc import abstractmethod
from pycromanager.execution_engine.kernel.device import Device
import numpy as np


class SingleAxisPositioner(Device):

    @abstractmethod
    def set_position(self, position: float) -> None:
        ...

    @abstractmethod
    def get_position(self) -> float:
        ...


class TriggerableSingleAxisPositioner(SingleAxisPositioner):
    """
    A special type of positioner that can accept a sequence of positions to move to when provided external TTL triggers
    """
    @abstractmethod
    def set_position_sequence(self, positions: np.ndarray) -> None:
        ...

    @abstractmethod
    def get_triggerable_sequence_max_length(self) -> int:
        ...


class DoubleAxisPositioner(Device):

        @abstractmethod
        def set_position(self, x: float, y: float) -> None:
            ...

        @abstractmethod
        def get_position(self) -> (float, float):
            ...

class TriggerableDoubleAxisPositioner(DoubleAxisPositioner):

        @abstractmethod
        def set_position_sequence(self, positions: np.ndarray) -> None:
            ...

        @abstractmethod
        def get_triggerable_sequence_max_length(self) -> int:
            ...

class Camera(Device):
    """
    Generic class for a camera and the buffer where it stores data
    """

    # TODO: maybe change these to attributes?
    @abstractmethod
    def set_exposure(self, exposure: float) -> None:
        ...

    @abstractmethod
    def get_exposure(self) -> float:
        ...

    @abstractmethod
    def arm(self, frame_count=None) -> None:
        """
        Arms the device before an start command. This optional command validates all the current features for
        consistency and prepares the device for a fast start of the Acquisition. If not used explicitly,
        this command will be automatically executed at the first AcquisitionStart but will not be repeated
        for the subsequent ones unless a feature is changed in the device.
        """
        ...

    @abstractmethod
    def start(self) -> None:
        ...

    # TODO: is it possible to make this return the number of images captured, to know about when to stop readout?
    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def is_stopped(self) -> bool:
        ...

    # TODO: perhaps this should be a seperate buffer class
    @abstractmethod
    def pop_image(self, timeout=None) -> (np.ndarray, dict):
        """
        Get the next image and metadata from the camera buffer. If timeout is None, this function will block until
        an image is available. If timeout is a number, this function will block for that many seconds before returning
        (None, None) if no image is available
        """
        ...

