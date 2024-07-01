""""
Base classes for devices that can be used by the execution engine
"""

from abc import abstractmethod
from pycromanager.acquisition.new.internal.device import Device


class SingleAxisActuator(Device):

    @abstractmethod
    def move(self, position: float) -> None:
        ...


class DoubleAxisActuator(Device):

    @abstractmethod
    def move(self, x: float, y: float) -> None:
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

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def is_stopped(self) -> bool:
        ...

    @abstractmethod
    def pop_image(self, timeout=None) -> (np.ndarray, dict):
        """
        Get the next image and metadata from the camera buffer. If timeout is None, this function will block until
        an image is available. If timeout is a number, this function will block for that many seconds before returning
        (None, None) if no image is available
        """
        ...

