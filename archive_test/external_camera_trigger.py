import numpy as np
from pycromanager import multi_d_acquisition_events, Acquisition


def external_trigger_fn(event):

    # TODO: send signal to external device here

    return event

with Acquisition(
    directory="/Users/henrypinkard/megllandump",
    name="tcz_acq",
    post_camera_hook_fn=external_trigger_fn,
) as acq:
    # Generate the events for a single z-stack
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
        channel_group="channel",
        channels=["DAPI", "FITC"],
        z_start=0,
        z_end=6,
        z_step=0.4,
        order="tcz",
    )
    acq.acquire(events)
