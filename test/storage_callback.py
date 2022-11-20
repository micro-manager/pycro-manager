from pycromanager import Acquisition, multi_d_acquisition_events
import numpy as np

def image_saved_fn(axes, dataset):
    pixels = dataset.read_image(**axes)
    print(np.mean(pixels))
    # Do something with image pixels/metadata

dir = 'C:/Program Files/Micro-Manager-2.0'
with Acquisition(directory=dir, name="tcz_acq", debug=False,
                 image_saved_fn=image_saved_fn) as acq:
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        order="tcz",
    )
    acq.acquire(events)

