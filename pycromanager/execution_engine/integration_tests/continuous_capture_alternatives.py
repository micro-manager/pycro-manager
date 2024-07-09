import time

from pycromanager import start_headless
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from pycromanager.execution_engine.devices.implementations.micromanager.mm_device_implementations import MicroManagerCamera
import os
from pycromanager.execution_engine.kernel.executor import ExecutionEngine
from pycromanager.execution_engine.events.implementations.camera_events import (StartContinuousCapture,
                                                                                ReadoutImages, StopCapture)
from pycromanager.execution_engine.events.implementations.misc_events import Sleep
from pycromanager.execution_engine.kernel.data_handler import DataHandler
from pycromanager.execution_engine.storage.NDTiffandRAM import NDRAMStorage
import itertools


# TODO: make this a pytest startup fixture
mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)

executor = ExecutionEngine()

camera = MicroManagerCamera()
executor.set_debug_mode(True)


#### Version 1: submit start--readout--stop event_implementations in the same thread and manually stop readout from main thread
print('version 1')
storage = NDRAMStorage()
data_handler = DataHandler(storage=storage)



start_capture_event = StartContinuousCapture(camera=camera)
readout_images_event = ReadoutImages(camera=camera,
                                     image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                     data_handler=data_handler)
stop_capture_event = StopCapture(camera=camera)

_, readout_future, _ = executor.submit([start_capture_event, readout_images_event, stop_capture_event])
time.sleep(2)
readout_future.stop(await_completion=True)


# make sure 10 images were collected
while not {'time': 10} in storage:
    time.sleep(1)
data_handler.finish()





### Version 2: submit start--sleep--stop--readout event_implementations all in a single thread
# TODO: maybe need some synchronization here becuase the camera could stop before any images are ready..
print('version 2')
storage = NDRAMStorage()
data_handler = DataHandler(storage=storage)


start_capture_event = StartContinuousCapture(camera=camera)
readout_images_event = ReadoutImages(camera=camera,
                                     image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                     data_handler=data_handler, stop_on_empty=True)
stop_capture_event = StopCapture(camera=camera)
sleep_event = Sleep(time_s=2)

_, _, _, _ = executor.submit([start_capture_event, sleep_event, stop_capture_event, readout_images_event])


# make sure 10 images were collected
while not {'time': 10} in storage:
    time.sleep(1)
data_handler.finish()






### Version 3: readout images in parallel with capture
print('version 3')
storage = NDRAMStorage()
data_handler = DataHandler(storage=storage)


start_capture_event = StartContinuousCapture(camera=camera)
readout_images_event = ReadoutImages(camera=camera, num_images=10,
                                     image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                     data_handler=data_handler)
stop_capture_event = StopCapture(camera=camera)
sleep_event = Sleep(time_s=2)

_, _, _ = executor.submit([start_capture_event, sleep_event, stop_capture_event])
executor.submit(readout_images_event, use_free_thread=True)


# make sure 10 images were collected
while not {'time': 9} in storage:
    time.sleep(1)
data_handler.finish()




# Version 4: directly make API calls on camera and maybe interleave with readout
print('version 4')
storage = NDRAMStorage()
data_handler = DataHandler(storage=storage)


readout_images_event = ReadoutImages(camera=camera, num_images=10,
                                     image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                     data_handler=data_handler)
camera.arm(100)
camera.start()

executor.submit(readout_images_event)

# make sure 10 images were collected
while not {'time': 9} in storage:
    time.sleep(1)
data_handler.finish()





executor.shutdown()

# pritn all active threads
import threading

for thread in threading.enumerate():
    print(thread)