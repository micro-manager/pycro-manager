import threading
import pytest
import numpy as np
from pycromanager.acquisition.new.data_coords import DataCoordinates, DataCoordinatesIterator
from typing import Dict, Any
import time

# Assuming these are the correct imports based on the provided code
from pycromanager.acquisition.new.data_handler import DataHandler
from pycromanager.acquisition.new.base_classes.acq_events import AcquisitionEvent, DataProducingAcquisitionEvent
from pycromanager.acquisition.new.acq_future import AcquisitionFuture


class MockDataHandler(DataHandler):
    def __init__(self):
        self.data_storage = {}

    def put(self, coords: DataCoordinates, image: np.ndarray, metadata: Dict, future: AcquisitionFuture = None):
        self.data_storage[coords] = (image, metadata)

    def get(self, coords: DataCoordinates, return_data=True, return_metadata=True, processed=False):
        if coords not in self.data_storage:
            return None, None
        data, metadata = self.data_storage[coords]
        return (data if return_data else None, metadata if return_metadata else None)


class MockDataProducingAcquisitionEvent(DataProducingAcquisitionEvent):

    def __init__(self):
        super().__init__(image_coordinate_iterator=DataCoordinatesIterator.create(
            [{"time": 0}, {"time": 1}, {"time": 2}]))

    def execute(self):
        pass

@pytest.fixture
def mock_data_handler():
    return MockDataHandler()


@pytest.fixture
def mock_event():
    return MockDataProducingAcquisitionEvent()


@pytest.fixture
def acquisition_future(mock_event, mock_data_handler):
    return AcquisitionFuture(event=mock_event, data_handler=mock_data_handler)


def test_notify_execution_complete(acquisition_future):
    """
    Test that the acquisition future is notified when the event is complete
    """
    def complete_event():
        time.sleep(0.1)
        acquisition_future._notify_execution_complete(None)

    thread = threading.Thread(target=complete_event)
    thread.start()
    acquisition_future.await_execution()
    assert acquisition_future._event_complete


def test_notify_data(acquisition_future):
    """
    Test that the acquisition future is notified when data is added
    """
    coords = DataCoordinates({"time": 1})
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    acquisition_future._notify_data(coords, image, metadata)
    assert coords in acquisition_future._acquired_data_coordinates


def test_await_data(acquisition_future):
    """ Test that the acquisition future can wait for data to be added """
    coords = DataCoordinates({"time": 1})
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    def wait_and_notify():
        # Delay so that the await_data call is made before the data is added it it gets held in RAM
        # rather than retrieved from the storage by the data handler
        time.sleep(2)
        acquisition_future._notify_data(coords, image, metadata)
    thread = threading.Thread(target=wait_and_notify)
    thread.start()

    data, meta = acquisition_future.await_data(coords, return_data=True, return_metadata=True)
    assert np.array_equal(data, image)
    assert meta == metadata


def test_await_data_processed(acquisition_future):
    """ Test that the acquisition future can wait for processed data to be added """
    coords = DataCoordinates(time=1)
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    def wait_and_notify():
        # Delay so that the await_data call is made before the data is added it it gets held in RAM
        # rather than retrieved from the storage by the data handler
        time.sleep(2)
        acquisition_future._notify_data(coords, image, metadata, processed=True)
    thread = threading.Thread(target=wait_and_notify)
    thread.start()

    data, meta = acquisition_future.await_data(coords, return_data=True, return_metadata=True, processed=True)
    assert np.array_equal(data, image)
    assert meta == metadata


def test_await_data_saved(acquisition_future):
    coords = DataCoordinates(time=1)
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    def wait_and_notify():
        # Delay so that the await_data call is made before the data is added it it gets held in RAM
        # rather than retrieved from the storage by the data handler
        time.sleep(2)
        acquisition_future._notify_data(coords, image, metadata, stored=True)

    thread = threading.Thread(target=wait_and_notify)
    thread.start()

    data, meta = acquisition_future.await_data(coords, return_data=True, return_metadata=True, stored=True)
    assert np.array_equal(data, image)
    assert meta == metadata


def test_check_if_coordinates_possible(acquisition_future):
    coords = DataCoordinates({"time": 1})

    try:
        acquisition_future._check_if_coordinates_possible(coords)
    except ValueError:
        pytest.fail("Unexpected ValueError raised")

def test_check_if_coordinates_not_possible(acquisition_future):
    coords = DataCoordinates(time=1, channel='not_possible')

    with pytest.raises(ValueError):
        acquisition_future._check_if_coordinates_possible(coords)