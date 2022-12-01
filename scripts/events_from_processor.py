from pycromanager import Acquisition, multi_d_acquisition_events
import numpy as np


# this hook function can control the micro-manager core
def img_process_fn(image, metadata, bridge, event_queue):

    if not hasattr(img_process_fn, "counter"):
        img_process_fn.counter = 0

    if img_process_fn.counter < 10:
        evt = {"axes": {"time": 0, "n": img_process_fn.counter}}
        img_process_fn.counter += 1
        image[250:350, 100:300] = img_process_fn.counter * 10

    else:
        evt = None
    event_queue.put(evt)

    return image, metadata

acq = Acquisition(
    directory="/Users/henrypinkard/megllandump",
    name="acquisition_name",
    image_process_fn=img_process_fn,
)

# kick it off with a single event
acq.acquire({"axes": {"time": 0}})
