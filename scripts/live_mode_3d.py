from pycromanager import multi_d_acquisition_events
from pycromanager import Acquisition
from pycromanager import start_headless
import numpy as np
import napari
import os

mm_dir = "C:/Program Files/Micro-Manager-2.0/"
config_file = os.path.join(mm_dir, "MMConfig_demo.cfg")

start_headless(mm_dir, config_file=config_file, backend="python")
# start_headless(mm_dir, config_file=config_file, backend="java")

viewer = napari.Viewer()
# acq = PythonBackendAcquisition(napari_viewer=viewer)
# acq = JavaBackendAcquisition(name='test', directory=r'C:\Users\henry\Desktop\data')
# acq = Acquisition(name='test', directory=r'C:\Users\henry\Desktop\data')
acq = Acquisition(napari_viewer=viewer)


events = multi_d_acquisition_events(num_time_points=500,
                                    # time_interval_s=0,
                                    # z_start=0, z_end=10, z_step=1
                                    )
for e in events:
    e['exposure'] = np.random.randint(160)
    e['axes']['time'] = 0

acq.acquire(events)

acq.mark_finished()
napari.run()
acq.await_completion()
pass



