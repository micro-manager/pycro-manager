"""
Acquire a time series of Z-stacks, and use and image processor to make a second channel
showing the maximum intensity projection of the z stack
"""
from pycromanager import Acquisition, multi_d_acquisition_events
import numpy as np


def img_process_fn(image, metadata):
    # accumulate individual Z images
    if not hasattr(img_process_fn, "images"):
        img_process_fn.images = []
    img_process_fn.images.append(image)

    if len(img_process_fn.images) == num_z_steps:
        # if last image in z stack, make max intensity projection
        stack = np.stack(img_process_fn.images, axis=2)
        max_intensity_projection = np.max(stack, axis=2)
        projection_metadata = {
            "Axes": {"time": metadata["Axes"]["time"]},
            "Channel": "max_intensity_projection",
            "PixelType": metadata["PixelType"],
        }
        # clear list of accumulated images
        img_process_fn.images = []
        # propagate both original image and intensity project back to viewer
        return [(image, metadata), (max_intensity_projection, projection_metadata)]
    else:
        return image, metadata


events = multi_d_acquisition_events(
    num_time_points=10, time_interval_s=2, z_start=0, z_end=10, z_step=1
)
# read the number of z steps
num_z_steps = len(set([event["axes"]["z"] for event in events]))
save_dir = 'C:/Program Files/Micro-Manager-2.0'
save_name = "max_intesnity_acq"

with Acquisition(directory=save_dir, name=save_name, image_process_fn=img_process_fn) as acq:
    acq.acquire(events)
