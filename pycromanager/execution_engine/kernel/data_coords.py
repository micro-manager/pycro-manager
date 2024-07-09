from typing import Dict, Union, Optional, Iterator, List, Tuple, Iterable, Sequence, Any, Generator
from pydantic import BaseModel, Field, model_validator
from collections.abc import MutableMapping
import numpy as np

class DataCoordinates(BaseModel, MutableMapping):
    """
    Represents the coordinates of a piece of data (conventionally, a single 2D image). This is a convenience wrapper
    around a dictionary of axis name to axis value where the axis value can be either an integer or a string.
    """
    coordinate_dict: Dict[str, Union[int, str]] = Field(default_factory=dict)
    time: Optional[int] = None
    channel: Optional[str] = None
    z: Optional[int] = None

    def __init__(self, coordinate_dict: Dict[str, Union[int, str]] = None,
                 time: int = None, channel: str = None, z: int = None, **kwargs):
        # add coordinate dict to kwargs for pydantic type coercion
        if coordinate_dict is not None:
            kwargs['coordinate_dict'] = coordinate_dict
        if time is not None:
            kwargs['time'] = self._convert_to_python_int(time)
        if channel is not None:
            kwargs['channel'] = self._convert_to_python_int(channel)
        if z is not None:
            kwargs['z'] = self._convert_to_python_int(z)
        super().__init__(**kwargs)

        other_axis_names = [key for key in kwargs.keys() if key not in ['coordinate_dict', 'time', 'channel', 'z']]
        if coordinate_dict is not None and ((time is not None or channel is not None or z is not None) or
                                            len(other_axis_names) > 0):
            raise ValueError("If coordinate_dict is provided, time, channel, and z or other axis names "
                             "must not be provided.")

        # Handle the special case of time, channel, and z
        if time is not None:
            self.coordinate_dict['time'] = self._convert_to_python_int(time)
        if channel is not None:
            self.coordinate_dict['channel'] = self._convert_to_python_int(channel)
        if z is not None:
            self.coordinate_dict['z'] = self._convert_to_python_int(z)

        # set other axis names as attributes
        for key in other_axis_names: # if theyre in kwargs
            setattr(self, key, kwargs[key])
        # if theyre in coordinate_dict
        if coordinate_dict is not None:
            for key, value in coordinate_dict.items():
                if not hasattr(self, key):
                    setattr(self, key, value)


    class Config:
        validate_assignment = True
        extra = 'allow' # allow setting of other axis names as attributes that are not in the model

    @staticmethod
    def _convert_to_python_int(value):
        if isinstance(value, np.integer):
            return int(value)
        return value

    def __setitem__(self, key: str, value: Union[int, str, np.integer]) -> None:
        value = self._convert_to_python_int(value)
        self.coordinate_dict[key] = value
        setattr(self, key, value)

    def __setattr__(self, key: str, value: Union[int, str, np.integer]) -> None:
        value = self._convert_to_python_int(value)
        super().__setattr__(key, value)
        if not key.startswith('_'):
            self.coordinate_dict[key] = value

    @model_validator(mode="before")
    def _set_coordinates(cls, values):
        coordinate_dict = values.get('coordinate_dict', {})
        for key, value in coordinate_dict.items():
            coordinate_dict[key] = cls._convert_to_python_int(value)
            if key not in values:
                values[key] = coordinate_dict[key]
        return values

    def __getitem__(self, key: str) -> Union[int, str]:
        return self.coordinate_dict[key]

    def __delitem__(self, key: str) -> None:
        del self.coordinate_dict[key]

    def __contains__(self, key: str) -> bool:
        return key in self.coordinate_dict

    def __delattr__(self, item: str) -> None:
        super().__delattr__(item)
        if item in self.coordinate_dict:
            del self.coordinate_dict[item]

    def __eq__(self, other):
        if isinstance(other, DataCoordinates):
            return self.coordinate_dict == other.coordinate_dict
        elif isinstance(other, dict):
            return self.coordinate_dict == other
        return NotImplemented

    def __hash__(self):
        return hash(frozenset(self.coordinate_dict.items()))

    def __len__(self):
        return len(self.coordinate_dict)

    def __iter__(self):
        return iter(self.coordinate_dict)

    def __repr__(self) -> str:
        # Provide a concise and clear representation
        return f"DataCoordinates({self.coordinate_dict})"

    def __str__(self) -> str:
        # Provide a user-friendly string representation
        return f"DataCoordinates: {self.coordinate_dict}"


class DataCoordinatesIterator:
    @classmethod
    def create(cls, image_coordinate_iterable: Union[Iterable[DataCoordinates], Iterable[Dict[str, Union[int, str]]],
                                                     DataCoordinates,
                                                     Dict[str, Union[Union[int, str], 'DataCoordinatesIterator']]]):
        """
        Autoconvert ImageCoordinates, dictionaries, or Iterables thereof to ImageCoordinatesIterator

        :param image_coordinate_iterable: an ImageCoordinates object, a dictionary,
                an iterable of ImageCoordinates or dictionaries, or an ImageCoordinatesIterator. Valid options include
                a list of ImageCoordinates, a list of dictionaries, a generator of ImageCoordinates,
                a generator of dictionaries, etc.
        """
        if isinstance(image_coordinate_iterable, cls):
            return image_coordinate_iterable

        if isinstance(image_coordinate_iterable, DataCoordinates):
            image_coordinate_iterable = [image_coordinate_iterable]
        elif isinstance(image_coordinate_iterable, dict):
            image_coordinate_iterable = [image_coordinate_iterable]

        instance = super().__new__(cls)
        instance._initialize(image_coordinate_iterable)
        return instance

    def __new__(cls, *args, **kwargs):
        raise TypeError(
            "ImageCoordinatesIterator cannot be instantiated directly. Use ImageCoordinatesIterator.create() instead.")


    def might_produce_coordinates(self, coordinates: DataCoordinates) -> Optional[bool]:
        """
        Check if this iterator might produce the given coordinates. If this iterator is backed by a finite list of
        ImageCoordinates, this can be checked definitively. If it is backed by something infinite (like a generator),
        it will only be possible if more information about the generator is known (e.g. it produces {time: 0}, {time:1},
        and continues incrementing).

        If not possible to determine definitely, return None
        """
        if isinstance(self._backing_iterable, Sequence):
            return any(self._compare_coordinates(coord, coordinates) for coord in self._backing_iterable)

        # TODO: cases where you pass in an object that increments with a known pattern

        # For non-sequences (like generators), we can't determine definitely without further information
        return None

    def is_finite(self) -> bool:
        """
        Check if this iterator is finite (i.e. will eventually run out of elements)
        """
        return isinstance(self._backing_iterable, Sequence)

    @staticmethod
    def _compare_coordinates(coord, target):
        if isinstance(coord, dict):
            coord = DataCoordinates(**coord)
        return all(getattr(coord, key) == value for key, value in target.__dict__.items())


    def _initialize(self, data):
        self._backing_iterable = data
        self._iterator = iter(data)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            next_item = next(self._iterator)
            if isinstance(next_item, dict):
                return DataCoordinates(**next_item)
            elif isinstance(next_item, DataCoordinates):
                return next_item
            else:
                raise TypeError(f"Unexpected item type: {type(next_item)}. Expected ImageCoordinates or dict.")
        except StopIteration:
            raise
        except Exception as e:
            raise TypeError(f"Error processing next item: {str(e)}")


    def __str__(self):
        if isinstance(self._backing_iterable, Generator):
            return "DataCoordinatesIterator(dynamic)"
        elif isinstance(self._backing_iterable, Sequence):
            coords_strs = [str(coord) if isinstance(coord, DataCoordinates)
                           else str(DataCoordinates(**coord))
                           for coord in self._backing_iterable]
            return f"DataCoordinatesIterator({', '.join(coords_strs)})"
        else:
            return "DataCoordinatesIterator(unknown)"

    __repr__ = __str__
