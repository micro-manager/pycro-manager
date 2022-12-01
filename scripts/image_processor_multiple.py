import numpy as np
from pycromanager import multi_d_acquisition_events, Acquisition
import copy


def img_process_fn(image, metadata):

    image2 = np.array(image, copy=True)
    image2 = np.swapaxes(image2, 0, 1)
    md_2 = copy.deepcopy(metadata)

    image[250:350, 100:300] = np.random.randint(0, 4999)

    if metadata["Channel"] == "DAPI":
        image[:100, :100] = 0
        image2[:100, :100] = 0
    else:
        image[-100:, -100:] = 0
        image2[-100:, -100:] = 0

    # metadata['Axes']['l'] = 0
    md_2["Channel"] = "A_new_channel"

    return [(image, metadata), (image2, md_2)]

with Acquisition(
    directory="/Users/henrypinkard/megllandump", name="tcz_acq", image_process_fn=img_process_fn
) as acq:
    # Generate the events for a single z-stack
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
        channel_group="Channel",
        channels=["DAPI", "FITC"],
        order="tc",
    )
    acq.acquire(events)
