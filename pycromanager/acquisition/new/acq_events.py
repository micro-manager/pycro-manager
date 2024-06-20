from typing import Union, List, Tuple, Callable, Dict
from pydantic import BaseModel
import numpy as np
from typing_extensions import Protocol, runtime_checkable
from queue import Queue
from threading import Event
from typing import Iterable
from pycromanager.acquisition.new.devices import Camera

from pycromanager.acquisition.new.image_coords import ImageCoordinates


def atomic_instruction(cls):
    cls.atomic_instruction = True
    return cls

@atomic_instruction
class DeviceInstruction(BaseModel):
    """
    Represents an instruction to a device. i.e.
    """
    device_action: Callable # bound method of a device
    # TODO: enforce that arguments must be primitives or arrays?
    args: Tuple

    def execute(self):
        """
        Execute the device instruction
        """
        return self.device_action(*self.args)

@atomic_instruction
class ReadoutImages(BaseModel):
    """
    Readout one or more images (and associated metadata) from a camera

    Attributes:
        num_images (int): The number of images to read out.
        camera (Camera): The camera object to read images from.
        image_coordinate_iterator (Iterable[ImageCoordinates]): An iterator or list of ImageCoordinates objects, which
            specify the coordinates of the images that will be read out.
    """
    num_images: int
    camera: Camera
    image_coordinate_iterator: Iterable[ImageCoordinates]

    def execute(self, output_queue: Queue, stop_event: Event):
        """
        Readout images from the camera
        """
        for image_number, image_coordinates in zip(range(self.num_images), self.image_coordinates):
            while True:
                if stop_event.is_set():
                    self.camera.stop()
                    break
                image, metadata = self.camera.pop_image(timeout=0.01) # only block for 10 ms so stop event can be checked
                if image is not None:
                    output_queue.put((image_coordinates, image, metadata))
                    break
            if stop_event.is_set():
                break
        self.camera.stop()


class CaptureImages(BaseModel):
    """
    Special device instruction that captures images from a camera
    """
    num_images: int
    device: Camera
    image_coordinates: ImageCoordinates # coordinates of the image(s) produced by this device instruction

    def execute(self):
        """
        Capture images from the camera
        """
        for _ in range(self.num_images):
            self.device.arm()
            self.device.start()
            image, metadata = self.device.pop_image()





class AcquisitionEvent(BaseModel):
    # list of device instructions, to be executed in order
    device_instructions: List[DeviceInstruction] = None
    # # list of config groups to be applied
    # config_group: Union[ConfigGroupSetting, List[ConfigGroupSetting]]


    # TODO: how to handle state
    # TODO: how to handle min_start_time



    def add_device_instructions(self, device_action: Callable, *args: Union[Tuple, List],
                                image_coordinates: ImageCoordinates = None
                                ) -> 'AcquisitionEvent':
        """
        Add a device instruction to this event. A device instruction is a callable bound method of a device
        and a list of arguments to pass to that method.

        :param device_action: the callable bound method of a device
        :param args: the arguments to pass to the method
        :param image_coordinates: If this device instruction produces an image, the coordinates of that image
        """
        if self.device_instructions is None:
            self.device_instructions = []
        self.device_instructions.append(DeviceInstruction(device_action=device_action, args=args,
                                                          image_coordinates=image_coordinates))
        return self

    # def _convert_to_old_style_json(self):
    #     data = {}
    #
    #     # if e.is_acquisition_finished_event():
    #     #     data["special"] = "acquisition-end"
    #     #     return data
    #     # elif e.is_acquisition_sequence_end_event():
    #     #     data["special"] = "sequence-end"
    #     #     return data
    #
    #     # TODO: restore this
    #     # if e.miniumumStartTime_ms_:
    #     #     data["min_start_time"] = e.miniumumStartTime_ms_ / 1000
    #
    #     if isinstance(self.config_group, list):
    #         raise Exception("old style events only support one config group")
    #     elif self.config_group is not None:
    #         data["config_group"] = [self.config_group.name, self.config_group.preset]
    #
    #     for device_instruction in self.device_instructions:
    #         if device_instruction.device == MicroManagerCamera and device_instruction.device.action == "set_exposure":
    #             data["exposure"] = device_instruction.device.args[0]
    #
    #     if self.image_coordinates:
    #         data["axes"] = {axis.name: axis.value for axis in self.image_coordinates}
    #
    #
    #     for device in self.device_instructions:
    #         if device == MicroManagerStage and device.action == "set_position":
    #             data["z"] = device.args[0]
    #
    #     for device in self.device_instructions:
    #         if device == MicroManagerXYStage and device.action == "set_position":
    #             data["x"] = device.args[0]
    #             data["y"] = device.args[1]
    #
    #     # if e.camera_:
    #     #     data["camera"] = e.camera_
    #
    #     # get camera from device instructions
    #     for device in self.device_instructions:
    #         if device == MicroManagerCamera:
    #             data["camera"] = device.name
    #
    #     # TODO device names
    #     # props = [[t.dev, t.prop, t.val] for t in e.properties_]
    #     # if props:
    #     #     data["properties"] = props
    #
    #     return data
    #
    # @staticmethod
    # def create_from_old_style_json(data, acq):
    #     if "special" in data:
    #         if data["special"] == "acquisition-end":
    #             return AcquisitionEvent.create_acquisition_finished_event(acq)
    #         elif data["special"] == "sequence-end":
    #             return AcquisitionEvent.create_acquisition_sequence_end_event(acq)
    #
    #     event = AcquisitionEvent(acq)
    #
    #     if "axes" in data:
    #         for axisLabel, value in data["axes"].items():
    #             event.axisPositions_[axisLabel] = value
    #
    #     if "min_start_time" in data:
    #         event.miniumumStartTime_ms_ = int(data["min_start_time"] * 1000)
    #
    #     if "timeout_ms" in data:
    #         event.timeout_ms_ = float(data["timeout_ms"])
    #
    #     if "config_group" in data:
    #         event.configGroup_ = data["config_group"][0]
    #         event.configPreset_ = data["config_group"][1]
    #
    #     if "exposure" in data:
    #         event.exposure_ = float(data["exposure"])
    #
    #     # if "timeout_ms" in data:
    #     #     event.slmImage_ = float(data["timeout_ms"])
    #
    #     if "stage_positions" in data:
    #         for stagePos in data["stage_positions"]:
    #             event.set_stage_coordinate(stagePos[0], stagePos[1])
    #
    #     if "z" in data:
    #         event.zPosition_ = float(data["z"])
    #
    #     if "stage" in data:
    #         deviceName = data["stage"]["device_name"]
    #         position = data["stage"]["position"]
    #         event.axisPositions_[deviceName] = float(position)
    #         if "axis_name" in data["stage"]:
    #             axisName = data["stage"]["axis_name"]
    #             event.stageDeviceNamesToAxisNames_[deviceName] = axisName
    #
    #     # # Assuming XYTiledAcquisition is a class and AcqEngMetadata is a class or module with constants
    #     # if isinstance(event.acquisition_, XYTiledAcquisition):
    #     #     posIndex = event.acquisition_.getPixelStageTranslator().getPositionIndices(
    #     #         [int(event.axisPositions_[AcqEngMetadata.AXES_GRID_ROW])],
    #     #         [int(event.axisPositions_[AcqEngMetadata.AXES_GRID_COL])])[0]
    #     #     xyPos = event.acquisition_.getPixelStageTranslator().getXYPosition(posIndex).getCenter()
    #     #     event.xPosition_ = xyPos.x
    #     #     event.yPosition_ = xyPos.y
    #
    #     if "x" in data:
    #         event.xPosition_ = float(data["x"])
    #
    #     if "y" in data:
    #         event.yPosition_ = float(data["y"])
    #
    #     if "slm_pattern" in data:
    #         event.slmImage_ = data["slm_pattern"]
    #
    #     if "camera" in data:
    #         event.camera_ = data["camera"]
    #
    #     if "tags" in data:
    #         tags = {key: value for key, value in data["tags"].items()}
    #         event.setTags(tags)
    #
    #     # if "properties" in data:
    #     #     for trip in data["properties"]:
    #     #         t = ThreeTuple(trip[0], trip[1], trip[2])
    #     #         event.properties_.add(t)
    #
    #     return event


class _AcquisitionFinishedEvent(BaseModel):
    pass

class _AcquisitionSequenceEndEvent(BaseModel):
    pass