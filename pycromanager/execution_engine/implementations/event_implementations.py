"""
This file contains implementations of AcquisitionEvents that can be used to build full experiments
"""
from typing import Iterable
import itertools
from pycromanager.acquisition.execution_engine.base_classes.acq_events import AcquisitionEvent, DataProducing
from pycromanager.acquisition.execution_engine.base_classes.devices import Camera
from pycromanager.acquisition.execution_engine.data_coords import DataCoordinates


class ReadoutImages(AcquisitionEvent, DataProducing):
    """
    Readout one or more images (and associated metadata) from a camera

    Attributes:
        num_images (int): The number of images to read out. If None, the readout will continue until the
            image_coordinate_iterator is exhausted or the camera is stopped and no more images are available.
        camera (Camera): The camera object to read images from.
        image_coordinate_iterator (Iterable[DataCoordinates]): An iterator or list of ImageCoordinates objects, which
            specify the coordinates of the images that will be read out, should be able to provide at least num_images
            elements.
    """
    num_images: int = None
    camera: Camera

    def execute(self):
        image_counter = itertools.count() if self.num_images is None else range(self.num_images)
        for image_number, image_coordinates in zip(image_counter, self.image_coordinate_iterator):
            while True:
                # TODO: read from state to check for cancel condition
                #  this can be made more efficient in the future with a execution_engine image buffer that provides callbacks
                # on a execution_engine image recieved so that polling can be avoided
                image, metadata = self.camera.pop_image(timeout=0.01) # only block for 10 ms so stop event can be checked
                if image is not None:
                    self.put_data(image_coordinates, image, metadata)
                    break
                # check stopping condition
                if self.camera.is_stopped():
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


class StartContinuousCapture(AcquisitionEvent):
    """
    Tell data-producing device to start capturing images continuously, until a stop signal is received
    """
    camera: Camera

    def execute(self):
        """
        Capture images from the camera
        """
        try:
            self.camera.arm()
            self.camera.start()
        except Exception as e:
            self.camera.stop()
            raise e

class StopCapture(AcquisitionEvent):
    """
    Tell data-producing device to start capturing images continuously, until a stop signal is received
    """
    camera: Camera

    def execute(self):
        self.camera.stop()
