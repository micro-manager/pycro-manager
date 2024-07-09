"""
Unit tests for DataHandler.
"""
import time
import pytest
import numpy as np
from typing import Dict

from pycromanager.execution_engine.kernel.data_handler import DataHandler
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from pycromanager.execution_engine.kernel.data_storage_api import DataStorageAPI

class MockDataStorage(DataStorageAPI):
    def __init__(self):
        self.data = {}
        self.metadata = {}
        self.finished = False

    def put(self, coords: DataCoordinates, image: np.ndarray, metadata: Dict):
        self.data[coords] = image
        self.metadata[coords] = metadata

    def get_data(self, coords: DataCoordinates) -> np.ndarray:
        return self.data.get(coords)

    def get_metadata(self, coords: DataCoordinates) -> Dict:
        return self.metadata.get(coords)

    def close(self):
        pass

    def finish(self):
        self.finished = True

    def __contains__(self, coords: DataCoordinates) -> bool:
        return coords in self.data


@pytest.fixture
def mock_data_storage():
    return MockDataStorage()


@pytest.fixture
def data_handler(mock_data_storage):
    return DataHandler(mock_data_storage)


def test_data_handler_put_and_get(data_handler):
    """
    Test that DataHandler can put and get data correctly.
    """
    coords = DataCoordinates({"time": 1, "channel": "DAPI", "z": 0})
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    data_handler.put(coords, image, metadata, None)
    retrieved_image, retrieved_metadata = data_handler.get(coords)

    assert np.array_equal(retrieved_image, image)
    assert retrieved_metadata == metadata


def test_data_handler_processing_function(data_handler, mock_data_storage):
    """
    Test that DataHandler can process data using a provided processing function, and that
    data_handler.get() returns the processed data not the original data.
    """
    def process_function(coords, image, metadata):
        return coords, image * 2, metadata

    handler_with_processing = DataHandler(mock_data_storage, process_function)

    coords = DataCoordinates({"time": 1, "channel": "DAPI", "z": 0})
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    handler_with_processing.put(coords, image, metadata, None)

    retrieved = handler_with_processing.get(coords, processed=True)
    # wait until the data has been processed
    start_time = time.time()
    while retrieved is None:
        time.sleep(0.05)
        retrieved = handler_with_processing.get(coords, processed=True)
        if time.time() - start_time > 10:
            raise TimeoutError("Data was not processed within 10 seconds")
    retrieved_image, retrieved_metadata = retrieved

    assert np.array_equal(retrieved_image, image * 2)
    assert retrieved_metadata == metadata


def test_data_handler_shutdown(data_handler, mock_data_storage):
    """
    Test that DataHandler signals the storage_implementations to finish correctly.
    """
    data_handler.finish()  # Signal to finish
    data_handler.join()

    assert mock_data_storage.finished
def test_data_handler_with_acquisition_future(data_handler):
    """
    Test that DataHandler interacts correctly with AcquisitionFuture.
    """

    class MockAcquisitionFuture():
        def _notify_data(self, coords, data, metadata, processed, stored):
            self.notified = True

    future = MockAcquisitionFuture()
    coords = DataCoordinates({"time": 1, "channel": "DAPI", "z": 0})
    image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    data_handler.put(coords, image, metadata, future)

    assert future.notified
