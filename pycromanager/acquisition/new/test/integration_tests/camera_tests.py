import time

from pycromanager import start_headless
from pycromanager.acquisition.new.data_coords import DataCoordinates
from pycromanager.acquisition.new.implementations.mm_device_implementations import MicroManagerCamera
import os
from pycromanager.acquisition.new.executor import ExecutionEngine
from pycromanager.acquisition.new.implementations.event_implementations import StartCapture, ReadoutImages, \
    StartContinuousCapture, StopCapture
from pycromanager.acquisition.new.data_handler import DataHandler
from pycromanager.acquisition.new.implementations.data_storage_implementations import NDStorage
import itertools


# TODO: make this a pytest startup fixture
mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)

camera = MicroManagerCamera()
executor = ExecutionEngine()






### Finite sequence
num_images = 100
storage = NDStorage()
data_handler = DataHandler(storage=storage)

start_capture_event = StartCapture(num_images=num_images, camera=camera)
readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                     image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
                                     data_handler=data_handler)

executor.submit([start_capture_event, readout_images_event])

image_count = 0
# TODO: monitor this with notifications

while not {'time': num_images - 1} in storage:
    time.sleep(1)

print('Finished first one')


#### Live mode
storage = NDStorage()
data_handler = DataHandler(storage=storage)

start_capture_event = StartContinuousCapture(camera=camera)
readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                     # TODO change this to infinite
                                     image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                     data_handler=data_handler)
stop_capture = StopCapture(camera=camera)

executor.submit([start_capture_event, readout_images_event])
time.sleep(2)
# Readout images is continuously running on one thread, so need to do this on another thread
executor.submit(stop_capture, use_free_thread=True)

image_count = 0
# TODO: monitor this with notifications

while not {'time': num_images - 1} in storage:
    time.sleep(1)

print('Finished second one')


num_images = 1
storage = NDStorage()
data_handler = DataHandler(storage=storage)

start_capture_event = StartCapture(num_images=num_images, camera=camera)
readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                     image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
                                     data_handler=data_handler)

executor.submit([start_capture_event, readout_images_event])

image_count = 0
# TODO: monitor this with notifications

while not {'time': num_images - 1} in storage:
    time.sleep(1)

print('Finished single image')