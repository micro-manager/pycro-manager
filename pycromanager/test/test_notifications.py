"""
Tests for notification API and asynchronous acquisition API
"""
from pycromanager import multi_d_acquisition_events, Acquisition, AcqNotification
import time
import numpy as np

# TODO: add tests for timing of blocking until different parts of the hardware sequence
# def test_async_images_read(launch_mm_headless, setup_data_folder):
#     start = time.time()
#     events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
#     with Acquisition(directory=setup_data_folder, show_display=False) as acq:
#         future = acq.acquire(events)
#
#         future.await_execution({'time': 5}, AcqNotification.Hardware.POST_HARDWARE)



def test_async_image_read(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
    with Acquisition(directory=setup_data_folder, show_display=False) as acq:
        future = acq.acquire(events)
        image = future.await_image_saved({'time': 5}, return_image=True)
        assert np.all(image == acq.get_dataset().read_image(time=5))

def test_async_image_read_sequence(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)
    with Acquisition(directory=setup_data_folder, show_display=False) as acq:
        future = acq.acquire(events)
        image = future.await_image_saved({'time': 5}, return_image=True)
        assert np.all(image == acq.get_dataset().read_image(time=5))

def test_async_images_read(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
    with Acquisition(directory=setup_data_folder, show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 7}, {'time': 8}, {'time': 9}], return_image=True)
        assert (len(images) == 3)

    # Make sure the returned images were the correct ones
    on_disk = [acq.get_dataset().read_image(time=t) for t in [7, 8, 9]]
    assert all([np.all(on_disk[i] == images[i]) for i in range(3)])

def test_async_images_read_sequence(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)
    with Acquisition(directory=setup_data_folder, show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 7}, {'time': 8}, {'time': 9}], return_image=True)
        assert (len(images) == 3)

    # Make sure the returned images were the correct ones
    on_disk = [acq.get_dataset().read_image(time=t) for t in [7, 8, 9]]
    assert all([np.all(on_disk[i] == images[i]) for i in range(3)])

