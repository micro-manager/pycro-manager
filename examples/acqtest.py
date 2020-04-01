import numpy as np
import json
import matplotlib.pyplot as plt
import multiprocessing
import threading
import queue
from inspect import signature

from pycromanager.acquire import Acquisition



def z_stack(start, stop, step):
    event_list = []
    for i, z in enumerate(np.arange(start, stop, step)):
        event = {}
        event['axes'] = {}
        event['axes']['z'] = i
        event['z'] = float(z)
        event['channel'] = {'group': 'Channel', 'config': 'FITC'}
        event['exposure'] = 100
        event_list.append(event)
    return event_list

def other_channel(existing_axes):
    event_list = []
    event = {}
    event['axes'] = existing_axes
    event['channel'] = {'group': 'Channel', 'config': 'DAPI'}
    event['exposure'] = 10
    event_list.append(event)
    return event_list

# def led_stack():
#     event_list = []
#     for i, l in enumerate(np.arange(100)):
#         event = {}
#         event['axes'] = {'led': i}
#         event['channel'] = {'group': 'Channel', 'config': 'DAPI'}
#         event['exposure'] = 10
#         event_list.append(event)
#     return event_list

events = z_stack(0, 100, 1)
first = events[0]
rest = events[1:]

#Version 1:
def hook_fn(event):
    return event

#Version 2:
def hook_fn(event, bridge, event_queue):
    return event

#Version 1:
def img_process_fn(image, metadata):
    image[250:350, 100:300] = np.random.randint(0, 4999)
    return image, metadata

#Version 2:
def img_process_fn_events(image, metadata, bridge, event_queue):
    #some operation on image to check for particular pattern in pixels
    if np.random.randint(2):
        event_queue.put(other_channel(metadata['AxesPositions']))
    if (len(rest) > 0):
        event_queue.put(rest.pop(0))
    else:
        event_queue.put(None)
    return image, metadata

acq = Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest',
                  image_process_fn=img_process_fn_events,
                 post_hardware_hook_fn=hook_fn)

acq.acquire(first)




