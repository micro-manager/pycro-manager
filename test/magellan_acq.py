from pycromanager import MagellanAcquisition, multi_d_acquisition_events
import numpy as np


def hook_fn(event):
    # if np.random.randint(4) < 2:
    #     return event
    return event

def img_process_fn(image, metadata):
    image[250:350, 100:300] = np.random.randint(0, 4999)
    return image, metadata

# magellan example
acq = MagellanAcquisition(
    # magellan_acq_index=0,
    magellan_explore=True,
    pre_hardware_hook_fn=hook_fn,
    image_process_fn=img_process_fn,
)
acq.await_completion()
