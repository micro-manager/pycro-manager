import pytest
from pydantic import ValidationError
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates, DataCoordinatesIterator
import numpy as np

def test_init_with_dict():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    assert coords.coordinate_dict == {"time": 1, "channel": "DAPI", "z": 0}

def test_init_with_dict_access_as_attr():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "z": 0})
    assert coords.time == 1

def test_init_with_individual_axes():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    assert coords.coordinate_dict == {"time": 1, "channel": "DAPI", "z": 0}

def test_init_with_both_raises_error():
    with pytest.raises(ValueError):
        DataCoordinates(coordinate_dict={"time": 1}, time=2)

def test_init_with_float():
    coords = DataCoordinates(time=1.0, channel="DAPI", z=0)
    assert coords.coordinate_dict == {"time": 1, "channel": "DAPI", "z": 0}
    assert coords.time == 1
    assert type(coords.time) is int

def test_init_exception_with_non_coercible_float_value():
    with pytest.raises(ValidationError):
        DataCoordinates(time=1.5, channel="DAPI", z=0)

def test_set_attr_exception_with_non_coercible_float_value():
    coords = DataCoordinates(channel="DAPI", z=0)
    with pytest.raises(ValidationError):
        coords.time = 1.5

def test_init_with_numpy():
    for time in np.arange(5):
        coords = DataCoordinates(time=time, channel="DAPI", z=0)
        assert coords.coordinate_dict == {"time": time, "channel": "DAPI", "z": 0}
        assert coords.time == time
        assert type(coords.time) is int

def test_attr_with_float():
    coords = DataCoordinates(channel="DAPI", z=0)
    coords.time = 1.0
    assert coords.coordinate_dict == {"time": 1, "channel": "DAPI", "z": 0}
    assert coords.time == 1
    assert type(coords.time) is int

def test_attr_with_numpy():
    for time in np.arange(5):
        coords = DataCoordinates(channel="DAPI", z=0)
        coords.time = time
        assert coords.coordinate_dict == {"time": time, "channel": "DAPI", "z": 0}
        assert coords.time == time
        assert type(coords.time) is int

def test_getitem():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    assert coords["time"] == 1
    assert coords["channel"] == "DAPI"
    assert coords["z"] == 0

def test_setitem():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    coords["time"] = 2
    assert coords["time"] == 2

def test_contains():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    assert "time" in coords
    assert "channel" in coords
    assert "z" in coords

def test_attr_access():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    assert coords.time == 1
    assert coords.channel == "DAPI"
    assert coords.z == 0

def test_equality():
    coords1 = DataCoordinates(time=1, channel="DAPI", z=0)
    coords2 = DataCoordinates(time=1, channel="DAPI", z=0)
    assert coords1 == coords2

    coords3 = {"time": 1, "channel": "DAPI", "z": 0}
    assert coords1 == coords3

def test_iteration():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    keys = [key for key in coords]
    assert keys == ["time", "channel", "z"]

def test_non_standard_axis_names():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    assert coords.coordinate_dict == {"time": 1, "channel": "DAPI", "depth": 10}
    assert coords.depth == 10

def test_validation_error_with_non_standard_axis_names_with_float():
    with pytest.raises(ValidationError):
        coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10.5})

def test_setitem_non_standard_axis():
    coords = DataCoordinates(time=1, channel="DAPI", z=0)
    coords["depth"] = 5
    assert coords["depth"] == 5
    assert coords.depth == 5

def test_contains_non_standard_axis():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    assert "depth" in coords
    assert coords.depth == 10

def test_attr_access_non_standard_axis():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    assert coords.depth == 10

def test_equality_non_standard_axis():
    coords1 = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    coords2 = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    assert coords1 == coords2

    coords3 = {"time": 1, "channel": "DAPI", "depth": 10}
    assert coords1 == coords3

def test_iteration_non_standard_axis():
    coords = DataCoordinates(coordinate_dict={"time": 1, "channel": "DAPI", "depth": 10})
    keys = [key for key in coords]
    assert keys == ["time", "channel", "depth"]
#######################################
#### Test DataCoordinatesIterator #####
#######################################

def test_data_coordinates_iterator_create():
    coords_list = [DataCoordinates(time=i, channel="DAPI", z=0) for i in range(3)]
    iterator = DataCoordinatesIterator.create(coords_list)
    assert iterator.is_finite()
    assert list(iterator) == coords_list

def test_data_coordinates_iterator_single():
    coord = DataCoordinates(time=1, channel="DAPI", z=0)
    iterator = DataCoordinatesIterator.create(coord)
    assert iterator.is_finite()
    assert list(iterator) == [coord]

def test_data_coordinates_iterator_dict():
    coord_dict = {"time": 1, "channel": "DAPI", "z": 0}
    iterator = DataCoordinatesIterator.create(coord_dict)
    assert iterator.is_finite()
    assert list(iterator) == [DataCoordinates(**coord_dict)]

def test_data_coordinates_iterator_contains():
    coords_list = [DataCoordinates(time=i, channel="DAPI", z=0) for i in range(3)]
    iterator = DataCoordinatesIterator.create(coords_list)
    coord = DataCoordinates(time=1, channel="DAPI", z=0)
    assert iterator.might_produce_coordinates(coord) == True
    coord_not_in_list = DataCoordinates(time=4, channel="DAPI", z=0)
    assert iterator.might_produce_coordinates(coord_not_in_list) == False


def test_consistent_integer_type():
    # Test initialization
    coords = DataCoordinates(time=np.int64(1), z=np.int32(2), channel="DAPI")

    # Check attribute access
    assert isinstance(coords.time, int)
    assert isinstance(coords.z, int)

    # Check dictionary-style access
    assert isinstance(coords['time'], int)
    assert isinstance(coords['z'], int)

    # Test setting via attribute
    coords.new_attr = np.int64(3)
    assert isinstance(coords.new_attr, int)
    assert isinstance(coords['new_attr'], int)

    # Test setting via dictionary-style access
    coords['another_attr'] = np.int32(4)
    assert isinstance(coords.another_attr, int)
    assert isinstance(coords['another_attr'], int)

    # Test with numpy array
    numpy_array = np.array([5, 6, 7], dtype=np.int64)
    coords.array_attr = numpy_array[0]
    assert isinstance(coords.array_attr, int)
    assert isinstance(coords['array_attr'], int)

    # Ensure all integer values are Python int
    for key, value in coords.coordinate_dict.items():
        if isinstance(value, (int, np.integer)):
            assert type(value) == int, f"Value for key '{key}' is not a Python int"
            assert type(coords[key]) == int, f"Getting '{key}' via [] doesn't return a Python int"
            assert type(getattr(coords, key)) == int, f"Getting '{key}' via attribute doesn't return a Python int"

    # Test that the original numpy types are converted
    assert type(coords.time) == int
    assert type(coords['time']) == int
    assert type(coords.z) == int
    assert type(coords['z']) == int
if __name__ == "__main__":
    pytest.main()