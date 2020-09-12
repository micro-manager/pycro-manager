import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events


with Acquisition('/Users/henrypinkard/megllandump', 'l_axis') as acq:
    #create one event for the image at each z-slice
    events = []
    for time in range(5):
        for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
            evt = {'axes': {'z': index, 'time': time},
                    'z': z_um,
                   'keep_shutter_open': True,
                   'min_start_time': 5 * time}
            events.append(evt)
        events.append({'keep_shutter_open': False, 'acquire_image': False})


    acq.acquire(events)
