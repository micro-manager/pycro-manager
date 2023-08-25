from pycromanager.acquisition.acq_eng_py.main.acquisition_py import Acquisition
from pycromanager import multi_d_acquisition_events
from pycromanager.acquisition.acq_eng_py.main.acquisition_event import AcquisitionEvent
import time

from pycromanager import start_headless
from RAMStorage import RAMDataStorage

mm_dir = "C:/Program Files/Micro-Manager-2.0"

start_headless(mm_dir, backend="python")


dataset = RAMDataStorage()
acq = Acquisition(dataset)

events = multi_d_acquisition_events(num_time_points=6, z_start=0, z_end=10, z_step=0.5)
events = [AcquisitionEvent.from_json(e, acq) for e in events]
acq.submit_event_iterator(iter(events))

acq.finish()

while not acq.are_events_finished():
    time.sleep(0.1)

dataset.as_array()

import napari
viewer = napari.Viewer()
viewer.add_image(dataset.as_array(), name='pycromanager acquisition')



print('completed')
