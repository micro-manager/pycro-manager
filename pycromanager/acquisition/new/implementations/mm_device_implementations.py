"""
Implementation of Micro-Manager devices.py in terms of the AcqEng bottom API
"""

from pycromanager.acquisition.new.apis.devices import Camera
from pycromanager.core import Core
import numpy as np
import pymmcore
import time
from concurrent.futures import ThreadPoolExecutor



class MicroManagerCamera(Camera):

    def __init__(self, device_name=None):
        """
        :param device_name: Name of the camera device in Micro-Manager. If None, and there is only one camera, that camera
        will be used. If None and there are multiple cameras, an error will be raised
        """
        self._core = Core()
        camera_names = self._core.get_loaded_devices_of_type(2) # 2 means camera...
        if not camera_names:
            raise ValueError("No cameras found")
        if device_name is None and len(camera_names) > 1:
            raise ValueError("Multiple cameras found, must specify device name")

        if device_name is None:
            self.device_name = camera_names[0]
        else:
            if device_name not in camera_names:
                raise ValueError(f"Camera {device_name} not found")
            self.device_name = device_name

        # Make a thread to execute calls to snap asynchronously
        # This may be removable in the the future with the new camera API if something similar is implemented at the core
        self._snap_executor = ThreadPoolExecutor(max_workers=1)
        self._last_snap = None
        self._snap_active = False


    def set_exposure(self, exposure: float) -> None:
        self._core.set_exposure(self.device_name, exposure)

    def get_exposure(self) -> float:
        return self._core.get_exposure(self.device_name)

    def arm(self, frame_count=None) -> None:
        if frame_count == 1:
            # nothing to prepare because snap will be called
            pass
        elif frame_count is None:
            # No need to prepare for continuous sequence acquisition
            pass
        else:
            self._core.prepare_sequence_acquisition(self.device_name)
        self._frame_count = 1

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
            self._core.set_camera_device(self.device_name)
            self._core.start_continuous_sequence_acquisition(0)
        else:
            self._core.start_sequence_acquisition(self._frame_count, 0, True)

    def stop(self) -> None:
        # This will stop sequences. There is not way to stop snap_image
        self._core.stop_sequence_acquisition(self.device_name)

    def is_stopped(self) -> bool:
        return self._core.is_sequence_running(self.device_name) and not self._snap_active

    def pop_image(self, timeout=None) -> (np.ndarray, dict):
        if self._frame_count != 1:
            md = pymmcore.Metadata()
            start_time = time.time()
            while True:
                pix = self._core.pop_next_image_md(0, 0, md)
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