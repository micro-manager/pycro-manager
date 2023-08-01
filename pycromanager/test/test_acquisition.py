import numpy as np
import pytest
import time
from pycromanager import Acquisition, Core, multi_d_acquisition_events
from pycromanager.acquisitions import AcqAlreadyCompleteException


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
    dataset.close()


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


def test_channel_noseq_acq(launch_mm_headless, setup_data_folder):
    """
    Test that channels are not sequenced when the exposure times are different

    """
    channels = ['DAPI', 'FITC', 'Rhodamine', 'Cy5']
    channel_exposures_ms = [5, 10, 15, 20]

    mmc = Core()
    mmc.set_exposure(2)
    mmc.set_property('LED', 'Sequence', 'On')

    events = multi_d_acquisition_events(channel_group='Channel-Multiband',
                                        channels=channels,
                                        channel_exposures_ms=channel_exposures_ms)

    def hook_fn(_events):
        assert check_acq_not_sequenced(_events), 'Sequenced acquisition is not built correctly'
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)

    # check that the exposure time was correctly set
    with acq.get_dataset() as ds:
        for channel, exposure_time in zip(channels, channel_exposures_ms):
            metadata = ds.read_metadata(channel=channel)
            assert metadata["Exposure"] == exposure_time


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
    Test that z-steps can be sequenced even if channels are not sequenced in TPCZ order acquisitions.
    Also test that channels exposure times are set correctly

    """
    channels = ['DAPI', 'FITC', 'Rhodamine', 'Cy5']
    channel_exposures_ms = [5, 10, 15, 20]

    mmc = Core()
    mmc.set_exposure(2)
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_property('LED', 'Sequence', 'Off')

    events = multi_d_acquisition_events(z_start=0, z_end=4, z_step=1,
                                        channel_group='Channel-Multiband',
                                        channels=channels,
                                        # channels may have different exposure time
                                        channel_exposures_ms=channel_exposures_ms,
                                        order='tpcz')

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 5), 'Sequenced acquisition is not built correctly'
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        acq.acquire(events)

    # check that the exposure time was correctly set
    with acq.get_dataset() as ds:
        for channel, exposure_time in zip(channels, channel_exposures_ms):
            metadata = ds.read_metadata(channel=channel, z=0)
            assert metadata["Exposure"] == exposure_time


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

    mmc = Core()
    mmc.set_exposure(1000)

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        events = multi_d_acquisition_events(1000)
        acq.acquire(events)
        time.sleep(10)
        acq.abort()

    # reset exposure time
    mmc.set_exposure(10)

    dataset = acq.get_dataset()
    assert(0 < len(dataset.index) < 100)

def test_abort_with_no_events(launch_mm_headless, setup_data_folder):
    """
    Test that aborting before any events processed doesnt cause hang or exception
    """
    with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
        acq.abort()
    assert True


def test_abort_from_external(launch_mm_headless, setup_data_folder):
    """
    Simulates the acquisition being shutdown from a remote source (e.g. Xing out the viewer)
    """
    with pytest.raises(AcqAlreadyCompleteException):
        with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
            events = multi_d_acquisition_events(num_time_points=6)
            acq.acquire(events[0])
            # this simulates an abort from the java side unbeknownst to python side
            # it comes from a new thread so it is non-blocking to the port
            acq._remote_acq.abort()
            for event in events[1:]:
                acq.acquire(event)
                time.sleep(5)

def test_abort_sequenced_zstack(launch_mm_headless, setup_data_folder):
    """
    Test that a hardware sequenced acquisition can be aborted mid-sequence

    """
    mmc = Core()
    mmc.set_property('Z', 'UseSequences', 'Yes')
    mmc.set_exposure(1000)

    def hook_fn(_events):
        assert check_acq_sequenced(_events, 1000), 'Sequenced acquisition is not built correctly'
        return _events

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     pre_hardware_hook_fn=hook_fn) as acq:
        events = multi_d_acquisition_events(z_start=0, z_end=999, z_step=1)
        acq.acquire(events)
        time.sleep(4)
        acq.abort()

    # reset exposure time
    mmc.set_exposure(10)

    dataset = acq.get_dataset()
    assert(len(dataset.index) < 1000)

def test_multi_channel_parsing(launch_mm_headless, setup_data_folder):
    """
    Test that datasets NDTiff datasets that are built up in real time parse channel names correctly
    """
    events = multi_d_acquisition_events(
        channel_group="Channel",
        channels=["DAPI", "FITC"],
    )

    with Acquisition(setup_data_folder, 'acq', show_display=False) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()

    assert False not in [channel in dataset.get_channel_names() for channel in ["DAPI", "FITC"]]
    dataset.close()
