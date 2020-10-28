import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events


with Acquisition("/Users/henrypinkard/megllandump", "l_axis") as acq:
    # create one event for the image at each z-slice
    for time in range(5):
        z_stack = []
        for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
            z_stack.append(
                {"axes": {"z": index, "time": time}, "z": z_um, "min_start_time": 5 * time}
            )

        acq.acquire(z_stack, keep_shutter_open=True)
