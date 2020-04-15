import numpy as np
import json
import matplotlib.pyplot as plt
import multiprocessing
import threading
import queue
from inspect import signature
import copy
import types

from pycromanager import Acquisition, multi_d_acquisition_events, Bridge


event_list = multi_d_acquisition_events(num_time_points=10, z_start=0, z_end=10, z_step=0.5)
# first = event_list.pop(0)
# rest = event_list

#Version 1:
def hook_fn(event):
    # if np.random.randint(4) < 2:
    #     return event
    return event

# #Version 2:
# def hook_fn(event, bridge, event_queue):
#     return event

#Version 1:
def img_process_fn(image, metadata):
    image[250:350, 100:300] = np.random.randint(0, 4999)
    return image, metadata


# #Version 2:
# def img_process_fn(image, metadata, bridge, event_queue):
#     if not hasattr(img_process_fn, 'events'):
#         setattr(img_process_fn, 'events', multi_d_acquisition_events(
#             num_time_points=10, z_start=0, z_end=10, z_step=0.5))
#     events = getattr(img_process_fn, 'events')
#     if len(events) != 0:
#         event_queue.put(events.pop(0))
#     return image, metadata

# with Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest',
#                   image_process_fn=img_process_fn,
#                  post_hardware_hook_fn=hook_fn) as acq:
#
#     acq.acquire(event_list[0])

# acq.await_completion()

# #magellan example
# with Acquisition(magellan_acq_index=0, post_hardware_hook_fn=hook_fn,
#                   image_process_fn=img_process_fn, debug=True) as acq:
#     pass
# acq.await_completion()




from pycromanager import Acquisition, multi_d_acquisition_events

# with Acquisition(directory='/Users/henrypinkard/megllandump', name='tcz_acq') as acq:
#     # Generate the events for a single z-stack
#     events = multi_d_acquisition_events(
#         num_time_points=3, time_interval_s=0,
#         channel_group='channel', channels=['DAPI', 'FITC'],
#         z_start=0, z_end=6, z_step=0.4,
#         order='tcz')
#     acq.acquire(events)

with Acquisition('/Users/henrypinkard/megllandump', 'l_axis') as acq:
    #create one event for the image at each z-slice
    events = []
    for time in range(5):
        for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
            evt = {
                    #'axes' is required. It is used by the image viewer and data storage to
                    #identify the acquired image
                    'axes': {'l': index, 'time': time},

                    #the 'z' field provides the z position in µm
                    'z': z_um}
            events.append(evt)

    acq.acquire(events)



