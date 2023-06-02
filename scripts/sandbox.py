from pycromanager import multi_d_acquisition_events, Acquisition
from copy import deepcopy
import time

num_time_points = 500
num_positions = 100

acq_completed = False
last_event_axes = {'position': 0, 'time': 0}

def check_acq_finished(axes, dataset):
    global acq_completed
    if axes == last_event_axes:
        acq_completed = True

acq =  Acquisition(
    directory=r'/Users/henrypinkard/tmp/test_acq',
    name='test_acq', 
    image_saved_fn=check_acq_finished,
    show_display=False
)

_events = multi_d_acquisition_events(num_time_points=num_time_points)

for p_idx in range(num_positions):
    t_start = time.time()

    acq_completed = False
    events = deepcopy(_events)
    for event in events:
        event['axes']['position'] = p_idx

    last_event_axes = events[-1]['axes']
    acq.acquire(events)

    # wait for acquisition to finish
    while not acq_completed:
        time.sleep(1)

    print(f'Position {p_idx} acquired in {time.time()-t_start:2.2f} seconds.')

