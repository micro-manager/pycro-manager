import numpy as np
import pytest
import time
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
    dataset.close()


def test_timelapse_seq_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 10), 'Sequenced acquisition is not built correctly'
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()
    assert np.all([dataset.has_image(time=t) for t in range(10)])
    dataset.close()


def test_empty_list_acq(launch_mm_headless, setup_data_folder):
    events = []

    with pytest.raises(Exception):
        with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
            acq.acquire(events)


def test_empty_dict_acq(launch_mm_headless, setup_data_folder):
    events = {}

    with pytest.raises(Exception):
        with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
            acq.acquire(events)


def test_empty_dict_list_acq(launch_mm_headless, setup_data_folder):
    events = [{}, {}]

    with pytest.raises(Exception):
        with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
            acq.acquire(events)


def test_empty_mda_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events()

    with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()
    assert dataset.axes == {}


def test_single_snap_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=1)

    with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()
    assert np.all([dataset.has_image(time=t) for t in range(1)])
    dataset.close()


def test_multi_d_acq(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
        channel_group="Channel",
        channels=["DAPI", "FITC"],
        z_start=0,
        z_end=5,
        z_step=1,
        order="tcz",
    )

    with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()

    for t in range(10):
        for z in range(6):
            for ch in ["DAPI", "FITC"]:
                assert dataset.has_image(time=t, channel=ch, z=z)

    data = dataset.as_array(axes=['time', 'channel', 'z'])
    assert data.shape[:-2] == (10, 2, 6)
    dataset.close()


def test_zstack_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that z-steps can be sequenced

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')

    events = multi_d_acquisition_events(z_start=0, z_end=9, z_step=1)

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_channel_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that channels can be sequenced

    """
    mmc = Core()
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'])

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_channel_z_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that both z-steps and channels can be sequenced in TPCZ order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpcz')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_z_channel_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that both z-steps and channels can be sequenced in TPZC order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpzc')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_channel_seq_z_noseq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that channels can be sequenced even if z-steps are not sequenced in TPZC order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'No')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpzc')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 4), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_channel_noseq_z_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that z-steps can be sequenced even if channels are not sequenced in TPZC order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'Off')

    events = multi_d_acquisition_events(z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        # channels may have different exposure time
                                        channel_exposures_ms=[5, 10, 15, 20],
                                        order='tpcz')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 5), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_time_channel_z_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that time, channels, and z can all be sequenced in TPCZ order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(num_time_points=2, time_interval_s=0,
                                        z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpcz')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_time_z_channel_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that time, channels, and z can all be sequenced in TPZC order acquisitions

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(num_time_points=2, time_interval_s=0,
                                        z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpzc')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, len(events)), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)


def test_time_noseq_z_channel_seq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that channels and z can be sequenced when timepoints are not sequenced

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(num_time_points=2, time_interval_s=2,
                                        z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=['DAPI', 'FITC', 'Rhodamine', 'Cy5'],
                                        order='tpzc')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 20), 'Sequenced acquisition is not built correctly'
        return None  # no need to actually acquire the data

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)

def test_time_noseq_z_seq_interval_acq(launch_mm_headless, setup_data_folder):
    """
    Test that timepoints are spaced by time_interval_s if the z/channel acquisition is sequenced

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')

    events = multi_d_acquisition_events(num_time_points=2, time_interval_s=5,
                                        z_start=0, z_end=4, z_step=1)

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 5), 'Sequenced acquisition is not built correctly'
        return _events

    t_start = time.time()
    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)
    t_end = time.time()

    assert(t_end-t_start > 5), 'Acquisition timing is not accurate'


def test_abort_sequenced_timelapse(launch_mm_headless, setup_data_folder):
    """
    Test that a hardware sequenced acquisition can be aborted mid-sequence

    """
    def hook_fn(_events):
        assert check_acq_sequenced(_events, 1000), 'Sequenced acquisition is not built correctly'
        return _events

    core = Core()
    core.set_exposure(1000)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        events = multi_d_acquisition_events(1000)
        acq.acquire(events)
        time.sleep(10)
        acq.abort()

    dataset = acq.get_dataset()
    assert(0 < len(dataset.index) < 100)

def test_abort_sequenced_zstack(launch_mm_headless, setup_data_folder):
    """
    Test that a hardware sequenced acquisition can be aborted mid-sequence

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 1000), 'Sequenced acquisition is not built correctly'
        return _events

    core = Core()
    core.set_exposure(1000)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        events = multi_d_acquisition_events(z_start=0, z_end=999, z_step=1)
        acq.acquire(events)
        time.sleep(4)
        acq.abort()

    dataset = acq.get_dataset()
    assert(len(dataset.index) < 1000)
