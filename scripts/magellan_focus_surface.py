from pycromanager import _Bridge, JavaBackendAcquisition
import numpy as np


def hook_fn(event):
    coordinates = np.array([event["x"], event["y"], event["z"]])

    return event



# magellan example
acq = JavaBackendAcquisition(magellan_acq_index=0, post_hardware_hook_fn=hook_fn)
acq.await_completion()
