from typing import Union, List, Tuple, Callable, Dict
from typing import Dict, Union, Optional, Iterator, List
from pydantic import BaseModel

class ImageCoordinates(BaseModel):
    """
    Represents the coordinates of an image. This is a convenience wrapper around a dictionary of axis name to axis value
    where the axis value can be either an integer or a string.
    """
    coordinate_dict: Dict[str, Union[int, str, Tuple[int, ...], Tuple[str, ...]]]

    def __init__(self, time: int = None, channel: str = None, z: int = None, **kwargs):
        # Initialize the BaseModel (this runs Pydantic validation and parsing)
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

# TODO make a nicer way to implement this...
# class ImageCoordinateIterator(BaseModel):
#     coordinate_dict: Dict[Tuple[str, Union[int, str, Tuple[int, ...], Tuple[str, ...]]]
#
#
#      def __iter__(self) -> Iterator['ImageCoordinates']:
#
#     def __next__(self) -> 'ImageCoordinates':

