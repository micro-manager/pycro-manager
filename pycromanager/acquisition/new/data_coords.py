from typing import Union, List, Tuple, Callable, Dict
from typing import Dict, Union, Optional, Iterator, List, Tuple, Iterable, Sequence
from pydantic import BaseModel
from pydantic.fields import Field

class DataCoordinates(BaseModel):
    """
    Represents the coordinates of a piece of data (conventionally, a single 2D image). This is a convenience wrapper
    around a dictionary of axis name to axis value where the axis value can be either an integer or a string.
    """
    coordinate_dict: Dict[str, Union[int, str]] = Field(default_factory=dict)

    def __init__(self, coordinate_dict: Dict[str, Union[int, str]] = None,
                 time: int = None, channel: str = None, z: int = None, **kwargs):
        if coordinate_dict is not None:
            self.coordinate_dict = coordinate_dict
            if time is not None or channel is not None or z is not None:
                raise ValueError("If coordinate_dict is provided, time, channel, and z must not be provided.")
        # if time/channel/z are not None, add them to the kwargs
        if time is not None:
            kwargs['time'] = time
        if channel is not None:
            kwargs['channel'] = channel
        if z is not None:
            kwargs['z'] = z
        super().__init__(**kwargs)

    def __getitem__(self, key: str) -> Union[int, str]:
        return self.coordinate_dict[key]

    def __setitem__(self, key: str, value: Union[int, str]) -> None:
        self.coordinate_dict[key] = value

    def __delitem__(self, key: str) -> None:
        del self.coordinate_dict[key]

    def __contains__(self, key: str) -> bool:
        return key in self.coordinate_dict

    def __getattr__(self, item: str) -> Union[int, str]:
        if item in self.coordinate_dict:
            return self.coordinate_dict[item]
        else:
            raise AttributeError(f"Attribute {item} not found")

    def __setattr__(self, key: str, value: Union[int, str]) -> None:
        if key == 'coordinate_dict':
            super().__setattr__(key, value)
        else:
            self.coordinate_dict[key] = value

    def __delattr__(self, item: str) -> None:
        if item in self.coordinate_dict:
            del self.coordinate_dict[item]
        else:
            super().__delattr__(item)

    def __eq__(self, other):
        if isinstance(other, DataCoordinates):
            return self.coordinate_dict == other.coordinate_dict
        elif isinstance(other, dict):
            return self.coordinate_dict == other
        return NotImplemented

    def __hash__(self):
        return hash(frozenset(self.coordinate_dict.items()))


class DataCoordinatesIterator:
    @classmethod
    def create(cls, image_coordinate_iterable: Union[Iterable[DataCoordinates], Iterable[Dict[str, Union[int, str]]],
                                                     DataCoordinates, Dict[str, Union[int, str],
    'DataCoordinatesIterator']]):
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
            return cls([image_coordinate_iterable])
        if isinstance(image_coordinate_iterable, dict):
            return cls([DataCoordinates(**image_coordinate_iterable)])

        instance = super().__new__(cls)
        instance._initialize(image_coordinate_iterable)
        return instance

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

    def __new__(cls, *args, **kwargs):
        raise TypeError(
            "ImageCoordinatesIterator cannot be instantiated directly. Use ImageCoordinatesIterator.create() instead.")

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
