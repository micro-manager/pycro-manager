import numpy as np
from pycromanager import Acquisition, multi_d_acquisition_events


def test_img_process_fn(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=3)

    def hook_fn(image, metadata):
        assert np.sum(image) > 0
        assert isinstance(metadata, dict)

        if metadata['Axes']["time"] == 1:
            image = np.zeros_like(image)

        return image, metadata

    with Acquisition(setup_data_folder, 'acq', show_display=False,
                     image_process_fn=hook_fn) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()
    data = dataset.as_array(axes=['time'])
    assert np.sum(data[0]) > 0
    assert np.sum(data[1]) == 0
    assert np.sum(data[2]) > 0
    dataset.close()


def test_img_process_fn_no_save(launch_mm_headless):
    events = multi_d_acquisition_events(num_time_points=3)

    def hook_fn(image, metadata):
        return None

    with Acquisition(directory=None, name='acq', show_display=False,
                     image_process_fn=hook_fn) as acq:
        acq.acquire(events)
        dataset = acq.get_dataset()  # Can this be moved out of the Acquisition context?

    assert dataset is None

def test_event_serialize_and_deserialize(launch_mm_headless):
    """
    Test that no information is lost when event is serialized and deserialized and passed through AcqEndJ
    """

    events = [
        {'axes': {'channel': 'DAPI'},
         'config_group': ['Channel', 'DAPI']},
        {'axes': {'view': 0},
         'camera': 'Camera'},
        {'axes': {'z': 4},
         'z': 123.34},
        {'axes': {'time': 0},
         'exposure': 100.0},
        {'axes': {'time': 1},
         'properties': [['DeviceName', 'PropertyName', 'PropertyValue']]},
        {'axes': {'z': 1},
         'stage_positions': [['ZDeviceName', 123.45]]},
    ]

    def hook_fn(event):
        test_event = events.pop(0)
        print('comparing\n', event, '\n', test_event)
        assert (event == test_event)
        return None  # cancel the event

    with Acquisition(show_display=False, pre_hardware_hook_fn=hook_fn) as acq:
        # copy list of events to avoid popping from original
        events_copy = [e for e in events]
        for test_event in events:
            acq.acquire(test_event)


