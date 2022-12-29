from pycromanager import Acquisition, multi_d_acquisition_events
import numpy as np


def hook_fn(event):

    return event


with Acquisition(
    directory="/Users/henrypinkard/tmp",
    name="acquisition_name",
    post_camera_hook_fn=hook_fn,
) as acq:
    acq.acquire(multi_d_acquisition_events(10))
