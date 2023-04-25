import os
from pycromanager import Core, Acquisition, multi_d_acquisition_events, start_headless

PORT1 = 4827
PORT2 = 5827


events1 = multi_d_acquisition_events(num_time_points = 100)
events2 = multi_d_acquisition_events(num_time_points = 50)

save_path = r"C:\Users\henry\Desktop\datadump"

acq1 = Acquisition(directory=save_path, name='acq1', port=PORT1, debug=True)
acq2 = Acquisition(directory=save_path, name='acq2', port=PORT1, debug=True)

acq1.acquire(events1)
acq2.acquire(events2)

acq1.mark_finished()
acq2.mark_finished()

acq1.await_completion()
acq2.await_completion()