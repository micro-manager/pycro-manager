from pycromanager import start_headless, stop_headless
from pycromanager.execution_engine.data_coords import DataCoordinates
from pycromanager.execution_engine.implementations.mm_device_implementations import MicroManagerCamera
import os
from pycromanager.execution_engine.executor import ExecutionEngine
from pycromanager.execution_engine.base_classes.acq_events import DataHandler
from pycromanager.execution_engine.implementations.data_storage_implementations import NDRAMStorage
from pycromanager.execution_engine.implementations.event_implementations import StartCapture, ReadoutImages
from pycromanager import Core

mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)


executor = ExecutionEngine()



camera = MicroManagerCamera()

num_images = 100
data_handler = DataHandler(storage=NDRAMStorage())

start_capture_event = StartCapture(num_images=num_images, camera=camera)
readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                     image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
                                     data_handler=data_handler)
executor.submit(start_capture_event)
future = executor.submit(readout_images_event)

future.await_execution()

data_handler.finish()

executor.shutdown()
stop_headless()



# # print all threads that are still a
# import threading
#
# for thread in threading.enumerate():
#     print(thread)
# pass