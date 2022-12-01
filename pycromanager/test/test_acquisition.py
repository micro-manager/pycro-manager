import numpy as np
from functools import partial
from pycromanager import Acquisition, multi_d_acquisition_events


def check_acq_sequenced(expected_num_events, events):
    assert isinstance(events, list)
    assert len(events) == expected_num_events

    return events


def check_acq_not_sequenced(events):
    assert isinstance(events, dict)

    return events


def test_timelapse_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.1)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=check_acq_not_sequenced) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()

    assert np.all([dataset.has_image(time=t) for t in range(10)])


def test_timelapse_seq_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=partial(check_acq_sequenced, 10)) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()

    assert np.all([dataset.has_image(time=t) for t in range(10)])
