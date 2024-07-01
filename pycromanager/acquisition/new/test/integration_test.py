from pycromanager import start_headless
from pycromanager.acquisition.new.data_coords import DataCoordinates
from pycromanager.acquisition.new.implementations.mm_device_implementations import MicroManagerCamera
import os
from pycromanager.acquisition.new.executor import ExecutionEngine
from pycromanager.acquisition.new.base_classes.acq_events import StartCapture, ReadoutImages, DataHandler


mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)


executor = ExecutionEngine()



camera = MicroManagerCamera()


num_images = 100
data_output_queue = DataHandler()

start_capture_event = StartCapture(num_images=num_images, camera=camera)
readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                     image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
                                     output_queue=data_output_queue)

executor.submit(start_capture_event)
executor.submit(readout_images_event)

image_count = 0
while True:
    coordinates, image, metadata = data_output_queue.get()
    image_count += 1
    print(f"Got image {image_count}  ", f'pixel mean {image.mean()}' )
    if image_count == num_images:
        break

executor.shutdown()


#
# events = []
# coord_list = [ImageCoordinates(time=t) for t in range(10)]
# for coord in coord_list:
#     events.append(ReadoutImages(num_images=1, camera=camera, image_coordinate_iterator=coord_list))
#
# with Acquisition(show_display=False, debug=True) as acq:
#     acq.acquire(events)



#
# with Acquisition(show_display=False, debug=True) as acq:
#     # copy list of events to avoid popping from original
#     acq.acquire(multi_d_acquisition_events(num_time_points=10))

