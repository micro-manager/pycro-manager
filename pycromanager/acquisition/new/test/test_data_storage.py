import pytest
import numpy as np
from pycromanager.acquisition.new.data_coords import DataCoordinates
from pycromanager.acquisition.new.implementations.data_storage_implementations import NDStorage
from pycromanager.acquisition.new.apis.data_storage import DataStorageAPI

@pytest.fixture(params=["tiff", "ram"])
def data_storage(request, tmp_path):
    return NDStorage(directory=str(tmp_path)) if request.param == "tiff" else NDStorage()

def test_fully_implements_protocol(data_storage):
    assert isinstance(data_storage, DataStorageAPI), "NDStorage does not fully implement DataStorageAPI"

def test_contains_integration(data_storage):
    data_coordinates = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    data_storage.put(data_coordinates, np.array([[1, 2], [3, 4]], dtype=np.uint16), {"some": "metadata"})

    assert data_coordinates in data_storage

def test_get_data_integration(data_storage):
    data_coordinates = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    expected_data = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    data_storage.put(data_coordinates, expected_data, {"some": "metadata"})

    result = data_storage.get_data(data_coordinates)
    assert np.array_equal(result, expected_data)

def test_get_metadata_integration(data_storage):
    data_coordinates = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    expected_metadata = {"some": "metadata"}
    data_storage.put(data_coordinates, np.array([[1, 2], [3, 4]], dtype=np.uint16 ), expected_metadata)

    result = data_storage.get_metadata(data_coordinates)
    assert result == expected_metadata

def test_put_integration(data_storage):
    data_coordinates = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    data = np.array([[1, 2], [3, 4]], dtype=np.uint16)
    metadata = {"some": "metadata"}

    data_storage.put(data_coordinates, data, metadata)
    stored_data = data_storage.get_data(data_coordinates)
    stored_metadata = data_storage.get_metadata(data_coordinates)
    assert np.array_equal(stored_data, data)
    assert stored_metadata == metadata

def test_finish_integration(data_storage):
    data_storage.finish()
    # Assertions to check if the dataset was marked as read-only can be added if there are methods or attributes to check this

def test_close_integration(data_storage):
    data_storage.close()
    # Assertions to check if resources were released can be added if there are methods or attributes to check this
