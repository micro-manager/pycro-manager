import numpy as np
from pycromanager import Acquisition, Core, multi_d_acquisition_events


def check_acq_sequenced(events, expected_num_events):
    return isinstance(events, list) and len(events) == expected_num_events


def check_acq_not_sequenced(events):
    return isinstance(events, dict)


def test_timelapse_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.1)

    def hook_fn(_events):
        assert check_acq_not_sequenced(_events)
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()

    assert np.all([dataset.has_image(time=t) for t in range(10)])


def test_timelapse_seq_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 10)
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()

    assert np.all([dataset.has_image(time=t) for t in range(10)])


def test_zstack_seq_acq(launch_mm_headless, setup_data_folder):
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 10)
        return None  # no need to actually acquire the data

    events = multi_d_acquisition_events(z_start=0, z_end=9, z_step=1)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)

