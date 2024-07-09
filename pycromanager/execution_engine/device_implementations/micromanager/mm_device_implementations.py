"""
Implementation of Micro-Manager device_implementations.py in terms of the AcqEng bottom API
"""

from pycromanager.execution_engine.kernel.device_types_base import (Device, Camera, TriggerableSingleAxisPositioner, TriggerableDoubleAxisPositioner)
from pycromanager.core import Core
import numpy as np
import pymmcore
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Union, Iterable



class MicroManagerDevice(Device):
    """
    Base class for all Micro-Manager device_implementations, which enables access to their properties

    The Micro-Manager device properties are exposed as attributes and discovered at runtime. Their names are
    not known in advance. This means this class can only have hard coded private attributes in order to avoid
    collisions
    """

    def __init__(self, device_name=None):
        super().__init__()
        # TODO: check if device with name exists
        self._device_name = device_name
        self._core = Core()

    def __getattr__(self, name):
        # First, get the core object using object's __getattribute__
        if hasattr(self, '_core'): # Will be None on initialization
            core = object.__getattribute__(self, '_core')
            device_name = object.__getattribute__(self, 'device_name')

            # Check if it's a device property
            if core.has_property(device_name, name):
                # If it is, return the property value
                return core.get_property(device_name, name)

        # If it's not a device property, use the default behavior
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        # Check if we're setting up initial attributes
        if name in ['_device_name', '_core']:
            return object.__setattr__(self, name, value)

        if not name.startswith('_'):
            # check if exists
            if not self._core.has_property(self._device_name, name):
                raise AttributeError(f"Device {self._device_name} does not have property {name}")
            # check if read only
            if self.is_property_read_only(self._device_name, name):
                raise ValueError("Read only properties cannot have values set")
        else:
            # private attributes are defined in the class
            object.__setattr__(self, name, value)

    def __dir__(self):
        attributes = set(super().__dir__())
        if hasattr(self, '_core') and self._device_name:
            try:
                device_properties = self._core.get_device_property_names(self._device_name)
                attributes.update(device_properties)
            except Exception as e:
                print(f"Warning: Failed to retrieve device properties: {e}")
        return sorted(attributes)

    def _get_mm_property_value(self, property_name: str):
        if not self._core.has_property(self._device_name, property_name):
            return None
        return self._core.get_property(self._device_name, property_name)

    def get_allowed_property_values(self, property_name: str) -> List[str]:
        # TODO
        return self._core.get_allowed_property_values(self._device_name, property_name)

    def is_property_read_only(self, property_name: str) -> bool:
        return self._core.is_property_read_only(self._device_name, property_name)

    def is_property_pre_init(self, property_name: str) -> bool:
        return self._core.is_property_pre_init(self._device_name, property_name)

    def is_property_sequenceable(self, property_name: str) -> bool:
        return self._core.is_property_sequenceable(self._device_name, property_name)

    def get_property_sequence_max_length(self, property_name: str) -> int:
        return self._core.get_property_sequence_max_length(self._device_name, property_name)

    def get_property_limits(self, property_name: str) -> (float, float):
        if not self._core.has_property_limits(self._device_name, property_name):
            return None
        return (self._core.get_property_lower_limit(self._device_name, property_name),
                self._core.get_property_upper_limit(self._device_name, property_name))

    def load_property_sequence(self, property_name: str, event_sequence: Iterable[Union[str, float, int]]):
        # TODO: check if within max sequence length
        # TODO: strvector stuff
        self._core.load_property_sequence(self._device_name, property_name, event_sequence)

    def start_property_sequence(self, property_name: str):
        self._core.start_property_sequence(self._device_name, property_name)

    def stop_property_sequence(self, property_name: str):
        self._core.stop_property_sequence(self._device_name, property_name)



class MicroManagerSingleAxisStage(MicroManagerDevice, TriggerableSingleAxisPositioner):

    def __init__(self, device_name=None):
        super().__init__(device_name=device_name)
        stage_names = self._core.get_loaded_devices_of_type(5)  # 5 means stage...
        if not stage_names:
            raise ValueError("No Stage device_implementations found")
        if device_name is None and len(stage_names) > 1:
            raise ValueError("Multiple Stage device_implementations found, must specify device name")

        if device_name is None:
            self._device_name = stage_names[0]
        else:
            if device_name not in stage_names:
                raise ValueError(f"Stage {device_name} not found")
            self._device_name = device_name

    def set_position(self, position: float) -> None:
        self._core.set_position(self._device_name, position)

    def get_position(self) -> float:
        return self._core.get_position(self._device_name)

    def set_position_sequence(self, positions: np.ndarray) -> None:
        if not self._core.is_stage_sequenceable(self._device_name):
            raise ValueError("Stage does not support sequencing")
        max_length = self._core.get_stage_sequence_max_length(self._device_name)
        if len(positions) > max_length:
            raise ValueError(f"Sequence length {len(positions)} exceeds maximum length {max_length}")
        z_sequence = pymmcore.DoubleVector()
        for z in positions:
            z_sequence.append(float(z))
        self._core.load_stage_sequence(self._device_name, z_sequence)

    def get_triggerable_sequence_max_length(self) -> int:
        if not self._core.is_stage_sequenceable(self._device_name):
            raise ValueError("Stage does not support sequencing")
        return self._core.get_stage_sequence_max_length(self._device_name)


class MicroManagerXYStage(MicroManagerDevice, TriggerableDoubleAxisPositioner):

    def __init__(self, device_name=None):
        super().__init__(device_name=device_name)
        self._core = Core()
        stage_names = self._core.get_loaded_devices_of_type(6)  # 5 means stage...
        if not stage_names:
            raise ValueError("No XYStage device_implementations found")
        if device_name is None and len(stage_names) > 1:
            raise ValueError("Multiple XYStage device_implementations found, must specify device name")

        if device_name is None:
            self._device_name = stage_names[0]
        else:
            if device_name not in stage_names:
                raise ValueError(f"XYStage {device_name} not found")
            self._device_name = device_name

    def set_position(self, x: float, y: float) -> None:
        self._core.set_xy_position(self._device_name, x, y)

    def get_position(self) -> (float, float):
        return self._core.get_xy_position(self._device_name)

    def set_position_sequence(self, positions: np.ndarray) -> None:
        if not self._core.is_xy_stage_sequenceable(self._device_name):
            raise ValueError("Stage does not support sequencing")
        max_length = self._core.get_xy_stage_sequence_max_length(self._device_name)
        if len(positions) > max_length:
            raise ValueError(f"Sequence length {len(positions)} exceeds maximum length {max_length}")
        x_sequence = pymmcore.DoubleVector()
        y_sequence = pymmcore.DoubleVector()
        for x, y in positions:
            x_sequence.append(float(x))
            y_sequence.append(float(y))
        self._core.load_xy_stage_sequence(self._device_name, x_sequence, y_sequence)

    def get_triggerable_sequence_max_length(self) -> int:
        if not self._core.is_xy_stage_sequenceable(self._device_name):
            raise ValueError("Stage does not support sequencing")
        return self._core.get_xy_stage_sequence_max_length(self._device_name)


class MicroManagerCamera(MicroManagerDevice, Camera):

    def __init__(self, device_name=None):
        """
        :param device_name: Name of the camera device in Micro-Manager. If None, and there is only one camera, that camera
        will be used. If None and there are multiple cameras, an error will be raised
        """
        super().__init__(device_name=device_name)
        self._core = Core()
        camera_names = self._core.get_loaded_devices_of_type(2) # 2 means camera...
        if not camera_names:
            raise ValueError("No cameras found")
        if device_name is None and len(camera_names) > 1:
            raise ValueError("Multiple cameras found, must specify device name")

        if device_name is None:
            self._device_name = camera_names[0]
        else:
            if device_name not in camera_names:
                raise ValueError(f"Camera {device_name} not found")
            self._device_name = device_name

        # Make a thread to execute calls to snap asynchronously
        # This may be removable in the the future with the execution_engine camera API if something similar is implemented at the core
        self._snap_executor = ThreadPoolExecutor(max_workers=1)
        self._last_snap = None
        self._snap_active = False


    def set_exposure(self, exposure: float) -> None:
        self._core.set_exposure(self._device_name, exposure)

    def get_exposure(self) -> float:
        return self._core.get_exposure(self._device_name)

    def arm(self, frame_count=None) -> None:
        if frame_count == 1:
            # nothing to prepare because snap will be called
            pass
        elif frame_count is None:
            # No need to prepare for continuous sequence acquisition
            pass
        else:
            self._core.prepare_sequence_acquisition(self._device_name)
        self._frame_count = frame_count

    def start(self) -> None:
        if self._frame_count == 1:
            # Execute this on a separate thread because it blocks
            def do_snap():
                self._snap_active = True
                self._core.snap_image()
                self._snap_active = False

            self._last_snap = self._snap_executor.submit(do_snap)
        elif self._frame_count is None:
            # set core camera to this camera because there's no version of this call where you specify the camera
            self._core.set_camera_device(self._device_name)
            self._core.start_continuous_sequence_acquisition(0)
        else:
            self._core.start_sequence_acquisition(self._frame_count, 0, True)

    def stop(self) -> None:
        # This will stop sequences. There is not way to stop snap_image
        self._core.stop_sequence_acquisition(self._device_name)

    def is_stopped(self) -> bool:
        return not self._core.is_sequence_running(self._device_name) and not self._snap_active

    def pop_image(self, timeout=None) -> (np.ndarray, dict):
        if self._frame_count != 1:
            md = pymmcore.Metadata()
            start_time = time.time()
            while True:
                try:
                    pix = self._core.pop_next_image_md(0, 0, md)
                except IndexError as e:
                    pix = None
                if pix is not None:
                    break
                # sleep for the shortest possible time, only to allow the thread to be interrupted and prevent
                # GIL weirdness. But perhaps this is not necessary
                # Reading out images should be the highest priority and thus should not be sleeping
                # This could all be made more efficient in the future with callbacks coming from the C level
                time.sleep(0.000001)
                if timeout is not None and time.time() - start_time > timeout:
                    return None, None

            metadata = {key: md.GetSingleTag(key).GetValue() for key in md.GetKeys()}
            return pix, metadata
        else:
            # wait for the snap to finish
            self._last_snap.result()

            # Is there no metadata when calling snapimage?
            metadata = {}
            return self._core.get_image(), metadata