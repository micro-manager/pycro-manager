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

b = Bridge()

p = b.get_studio().plugins()
p.get_autofocus_plugins()

pass
# event_list = multi_d_acquisition_events(num_time_points=10, z_start=0, z_end=10, z_step=0.5)
# # first = event_list.pop(0)
# # rest = event_list
#
# #Version 1:
# def hook_fn(event):
#     # if np.random.randint(4) < 2:
#     #     return event
#     return event
#
# # #Version 2:
# # def hook_fn(event, bridge, event_queue):
# #     return event
#
# #Version 1:
# def img_process_fn(image, metadata):
#     image[250:350, 100:300] = np.random.randint(0, 4999)
#     return image, metadata
#
#
# # #Version 2:
# # def img_process_fn(image, metadata, bridge, event_queue):
# #     if not hasattr(img_process_fn, 'events'):
# #         setattr(img_process_fn, 'events', multi_d_acquisition_events(
# #             num_time_points=10, z_start=0, z_end=10, z_step=0.5))
# #     events = getattr(img_process_fn, 'events')
# #     if len(events) != 0:
# #         event_queue.put(events.pop(0))
# #     return image, metadata
#
# # with Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest',
# #                   image_process_fn=img_process_fn,
# #                  post_hardware_hook_fn=hook_fn) as acq:
# #
# #     acq.acquire(event_list[0])
#
# # acq.await_completion()
#
#
#


