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
