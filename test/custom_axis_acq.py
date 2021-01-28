import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events


with Acquisition("/Users/henrypinkard/tmp", "l_axis") as acq:
    # create one event for the image at each z-slice
    events = []
    for time in range(5):
        for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
            evt = {
                #'axes' is required. It is used by the image viewer and data storage to
                # identify the acquired image
                "axes": {"l": index, "time": time},
                # the 'z' field provides the z position in µm
                "z": z_um,
            }
            events.append(evt)

    acq.acquire(events)
