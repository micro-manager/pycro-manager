"""
Tests for notification API and asynchronous acquisition API
"""
from pycromanager import multi_d_acquisition_events, Acquisition, AcqNotification
import time
import numpy as np

# Existing tests

def test_async_image_read(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
    with Acquisition(directory=setup_data_folder, name='test_async_image_read', show_display=False) as acq:
        future = acq.acquire(events)
        image = future.await_image_saved({'time': 5}, return_image=True)
        assert np.all(image == acq.get_dataset().read_image(time=5))
    acq.get_dataset().close()

def test_async_image_read_metadata_return(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
    with Acquisition(directory=setup_data_folder, name='test_async_image_read', show_display=False) as acq:
        future = acq.acquire(events)
        _, metadata = future.await_image_saved({'time': 5}, return_image=True, return_metadata=True)
        assert isinstance(metadata, dict)
    acq.get_dataset().close()

def test_async_image_read_sequence(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)
    with Acquisition(directory=setup_data_folder, name='test_async_image_read_sequence', show_display=False) as acq:
        future = acq.acquire(events)
        image = future.await_image_saved({'time': 5}, return_image=True)
        assert np.all(image == acq.get_dataset().read_image(time=5))
    acq.get_dataset().close()

def test_async_images_read(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0.5)
    with Acquisition(directory=setup_data_folder, name='test_async_images_read', show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 7}, {'time': 8}, {'time': 9}], return_image=True)
        assert (len(images) == 3)

    # Make sure the returned images were the correct ones
    on_disk = [acq.get_dataset().read_image(time=t) for t in [7, 8, 9]]
    assert all([np.all(on_disk[i] == images[i]) for i in range(3)])
    acq.get_dataset().close()

def test_async_images_read_sequence(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)
    with Acquisition(directory=setup_data_folder, name='test_async_images_read_sequence', show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 7}, {'time': 8}, {'time': 9}], return_image=True)
        assert (len(images) == 3)

    # Make sure the returned images were the correct ones
    on_disk = [acq.get_dataset().read_image(time=t) for t in [7, 8, 9]]
    assert all([np.all(on_disk[i] == images[i]) for i in range(3)])
    acq.get_dataset().close()

# New tests

def test_notification_callback_receives_notifications(launch_mm_headless, setup_data_folder):
    """
    Test that the notification callback function receives notifications during acquisition.
    """
    notifications = []
    def notification_callback(notification):
        notifications.append(notification)

    events = multi_d_acquisition_events(num_time_points=2)

    with Acquisition(directory=setup_data_folder, name='test_notification_callback',
                     notification_callback_fn=notification_callback, show_display=False) as acq:
        acq.acquire(events)

    assert len(notifications) > 0

def test_notification_callback_receives_start_notification(launch_mm_headless, setup_data_folder):
    """
    Test that the notification callback receives an acquisition start notification.
    """
    notifications = []
    def notification_callback(notification):
        notifications.append(notification)

    events = multi_d_acquisition_events(num_time_points=1)

    with Acquisition(directory=setup_data_folder, name='test_start_notification',
                     notification_callback_fn=notification_callback, show_display=False) as acq:
        acq.acquire(events)

    assert any(n.milestone == AcqNotification.Acquisition.ACQ_STARTED for n in notifications)

def test_notification_callback_receives_image_saved_notification(launch_mm_headless, setup_data_folder):
    """
    Test that the notification callback receives an image saved notification.
    """
    notifications = []
    def notification_callback(notification):
        notifications.append(notification)

    events = multi_d_acquisition_events(num_time_points=1)

    with Acquisition(directory=setup_data_folder, name='test_image_saved_notification',
                     notification_callback_fn=notification_callback, show_display=False) as acq:
        acq.acquire(events)

    assert any(n.milestone == AcqNotification.Image.IMAGE_SAVED for n in notifications)

def test_notification_callback_receives_finish_notification(launch_mm_headless, setup_data_folder):
    """
    Test that the notification callback receives an acquisition finished notification.
    """
    notifications = []
    def notification_callback(notification):
        notifications.append(notification)

    events = multi_d_acquisition_events(num_time_points=1)

    with Acquisition(directory=setup_data_folder, name='test_finish_notification',
                     notification_callback_fn=notification_callback, show_display=False) as acq:
        acq.acquire(events)

    assert any(n.milestone == AcqNotification.Acquisition.ACQ_EVENTS_FINISHED for n in notifications)

def test_acquisition_future_await_execution(launch_mm_headless, setup_data_folder):
    """
    Test that AcquisitionFuture.await_execution works correctly.
    """
    events = multi_d_acquisition_events(num_time_points=3, time_interval_s=0.1)

    with Acquisition(directory=setup_data_folder, name='test_await_execution',
                     show_display=False) as acq:
        future = acq.acquire(events)
        future.await_execution(milestone=AcqNotification.Hardware.POST_HARDWARE, axes={'time': 1})
        # If we reach this point without timing out, the test passes

def test_acquisition_future_await_image_saved_single(launch_mm_headless, setup_data_folder):
    """
    Test that AcquisitionFuture.await_image_saved works for a single image.
    """
    events = multi_d_acquisition_events(num_time_points=3, time_interval_s=0.1)

    with Acquisition(directory=setup_data_folder, name='test_await_image_single',
                     show_display=False) as acq:
        future = acq.acquire(events)
        image = future.await_image_saved({'time': 1}, return_image=True)
        assert isinstance(image, np.ndarray)
        assert image.shape == (512, 512)  # Assuming default image size

def test_acquisition_future_await_image_saved_multiple(launch_mm_headless, setup_data_folder):
    """
    Test that AcquisitionFuture.await_image_saved works for multiple images.
    """
    events = multi_d_acquisition_events(num_time_points=5, time_interval_s=0.1)

    with Acquisition(directory=setup_data_folder, name='test_await_image_multiple',
                     show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 2}, {'time': 3}, {'time': 4}], return_image=True)
        assert len(images) == 3
        assert all(isinstance(img, np.ndarray) for img in images)

def test_acquisition_future_image_consistency(launch_mm_headless, setup_data_folder):
    """
    Test that images returned by AcquisitionFuture match those saved on disk.
    """
    events = multi_d_acquisition_events(num_time_points=5, time_interval_s=0.1)

    with Acquisition(directory=setup_data_folder, name='test_image_consistency',
                     show_display=False) as acq:
        future = acq.acquire(events)
        images = future.await_image_saved([{'time': 2}, {'time': 3}, {'time': 4}], return_image=True)

        dataset = acq.get_dataset()
        on_disk = [dataset.read_image(time=t) for t in [2, 3, 4]]
        assert all(np.array_equal(on_disk[i], images[i]) for i in range(3))

    dataset.close()