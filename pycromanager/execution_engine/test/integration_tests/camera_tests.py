import time

from pycromanager import start_headless
from pycromanager.execution_engine.data_coords import DataCoordinates
from pycromanager.execution_engine.implementations.mm_device_implementations import MicroManagerCamera
import os
from pycromanager.execution_engine.executor import ExecutionEngine
from pycromanager.execution_engine.implementations.event_implementations import StartCapture, ReadoutImages, \
    StartContinuousCapture, StopCapture
from pycromanager.execution_engine.data_handler import DataHandler
from pycromanager.execution_engine.implementations.data_storage_implementations import NDRAMStorage
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







# ### Finite sequence
# num_images = 100
# storage = NDRAMStorage()
# data_handler = DataHandler(storage=storage)
#
# start_capture_event = StartCapture(num_images=num_images, camera=camera)
# readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
#                                      image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
#                                      data_handler=data_handler)
#
# executor.submit([start_capture_event, readout_images_event])
#
# image_count = 0
# # TODO: monitor this with notifications
#
# while not {'time': num_images - 1} in storage:
#     time.sleep(1)
#
# data_handler.finish()
# print('Finished first one')





# num_images = 1
# storage = NDRAMStorage()
# data_handler = DataHandler(storage=storage)
#
# start_capture_event = StartCapture(num_images=num_images, camera=camera)
# readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
#                                      image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
#                                      data_handler=data_handler)
#
# executor.submit([start_capture_event, readout_images_event])
#
# image_count = 0
# # TODO: monitor this with notifications
#
# while not {'time': num_images - 1} in storage:
#     time.sleep(1)
#
# data_handler.finish()
# print('Finished single image')




executor.shutdown()

# # pritn all active threads
# import threading
#
# for thread in threading.enumerate():
#     print(thread)