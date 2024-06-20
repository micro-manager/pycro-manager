from pycromanager import start_headless
from pycromanager.acquisition.new.acq_events import AcquisitionEvent, ReadoutImages
from pycromanager.acquisition.new.image_coords import ImageCoordinates
from pycromanager.acquisition.acq_eng_py.mm_device_implementations import MicroManagerCamera
import os
from pycromanager import Acquisition


mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)

camera = MicroManagerCamera()

events = []
coord_list = [ImageCoordinates(time=t) for t in range(10)]
for coord in coord_list:
    events.append(ReadoutImages(num_images=1, camera=camera, image_coordinate_iterator=coord_list))

with Acquisition(show_display=False, debug=True) as acq:
    acq.acquire(events)



#
# with Acquisition(show_display=False, debug=True) as acq:
#     # copy list of events to avoid popping from original
#     acq.acquire(multi_d_acquisition_events(num_time_points=10))

