"""
test the ability to acquisitions to have String axes instead of int ones
"""


from pycromanager import Acquisition, multi_d_acquisition_events
from pycromanager.acq_util import multi_d_acquisition_events_new


with Acquisition(directory="/Users/henrypinkard/tmp", name="NDTiff3.2_monochrome", debug=False) as acq:
    # Generate the events for a single z-stack
    events = multi_d_acquisition_events_new(
        num_time_points=8,
        time_interval_s=0,
        # channel_group="Channel",
        # channels=["DAPI", "FITC"],
        z_start=0,
        z_end=6,
        z_step=0.4,
        order="tcz",
    )
    acq.acquire(events)


