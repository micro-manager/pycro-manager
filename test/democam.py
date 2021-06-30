"""
This simple example uses pycromanager to vary exposure times with three repetitions
and can be run with Micro-manager's virtual DemoCamera / DCam device. The resulting
dataset is saved to 'democam_X/Full Resolution/democam_MagellanStack.tif` within the
current folder; consecutively numbered `X` separate individual runs of this script.
"""
from pycromanager import Acquisition


exposures = [100, 200, 300, 400]
with Acquisition(directory=".", name="democam") as acq:
    events = []
    for rep in range(3):
        for idx, exposure in enumerate(exposures):
            evt = {"axes": {"repetition": rep, "exposure": idx}, "exposure": exposure}
            events.append(evt)

    acq.acquire(events)
