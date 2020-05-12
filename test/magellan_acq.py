from pycromanager import Acquisition, multi_d_acquisition_events, Bridge
import numpy as np

def hook_fn(event):
    # if np.random.randint(4) < 2:
    #     return event
    return event

def img_process_fn(image, metadata):
    image[250:350, 100:300] = np.random.randint(0, 4999)
    return image, metadata

#magellan example
with Acquisition(magellan_acq_index=0, post_hardware_hook_fn=hook_fn,
                  image_process_fn=img_process_fn, debug=True) as acq:
    pass
acq.await_completion()