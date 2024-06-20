import numpy as np
from typing_extensions import Protocol, runtime_checkable

@runtime_checkable
class SingleAxisMovable(Protocol):
    def move(self, position: float) -> None:
        ...

@runtime_checkable
class DoubleAxisMovable(Protocol):
    def move(self, x: float, y: float) -> None:
        ...

@runtime_checkable
class Camera(Protocol):
    """
    Generic class for a camera and the buffer where it stores data
    """

    def set_exposure(self, exposure: float) -> None:
        ...

    def get_exposure(self) -> float:
        ...

    def arm(self, frame_count=None) -> None:
        """
        Arms the device before an start command. This optional command validates all the current features for
        consistency and prepares the device for a fast start of the Acquisition. If not used explicitly,
        this command will be automatically executed at the first AcquisitionStart but will not be repeated
        for the subsequent ones unless a feature is changed in the device.
        """
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def pop_image(self, timeout=None) -> (np.ndarray, dict):
        """
        Get the next image and metadata from the camera buffer. If timeout is None, this function will block until
        an image is available. If timeout is a number, this function will block for that many seconds before returning
        (None, None) if no image is available
        """
        ...

