"""

@author: Nick Anthony
"""
from __future__ import annotations
import abc
import json
import typing
from dataclasses import dataclass
import numpy as np


class _HookReg:
    """Stores deserialization hooks and combines them into `getHook`"""

    def __init__(self):
        self._hooks = []

    def addHook(self, f: typing.Callable[[typing.Any], typing.Any]):
        self._hooks.append(f)
        return self

    def getHook(self):
        def hook(d: dict):
            for h in self._hooks:
                origD = d
                d = h(d)
                if d is origD:
                    continue
                else:
                    return d
            return d

        return hook


class _JsonAble(abc.ABC):
    """
    Interface that must be implemented  for converting Micromanager PropertyMap objects to/from JSON.
    """

    @abc.abstractmethod
    def encode(self) -> dict:
        """This method should convert the property map class to a dictionary for jsonization"""
        pass

    @staticmethod
    @abc.abstractmethod
    def hook(d: object):
        """This function should try to identify if the provided JSON object (int, float, string, list, dict) represents an instance of this Property map class. If so then generate the class, otherwire return the input value unchanged."""
        pass


class Property(_JsonAble):
    """Represents a single property from a micromanager PropertyMap

    Attributes:
        pType: The type of the property. may be 'STRING', 'DOUBLE', or 'INTEGER'
        value: The value of the propoerty. Should match the type given in `pType`
    """

    pType: str
    value: typing.Union[str, int, float, typing.List[typing.Union[str, int, float]]]
    pTypes = {
        str: "STRING",
        float: "DOUBLE",
        int: "INTEGER",
    }  # Static collection of the possible datatypes.

    def __init__(self, value: typing.Union[str, int, float], pType: str = None):
        self.value = value
        if pType is None:
            self.pType = Property.pTypes[type(value)]
        else:
            self.pType = pType

    def encode(self) -> dict:
        """Convert this object to a PropertyMap dictionary."""
        d = {"type": self.pType}
        d["scalar"] = self.value
        return d

    @staticmethod
    def hook(d: dict):
        """Check if a dictionary represents an instance of this class and return a new instance. If this dict does not match
        the correct pattern then just return the original dict."""
        if "type" in d and d["type"] in Property.pTypes.values():
            if "scalar" in d:
                val = d["scalar"]
                return Property(pType=d["type"], value=val)
        return d


class PropertyArray(_JsonAble):
    def __init__(self, properties: typing.List[Property]):
        self._properties = properties

    def encode(self) -> dict:
        """Convert this object to a PropertyMap dictionary."""
        return {"type": self._properties[0].pType, "array": [i.value for i in self._properties]}

    @staticmethod
    def hook(d: dict):
        """Check if a dictionary represents an instance of this class and return a new instance. If this dict does not match
        the correct pattern then just return the original dict."""
        if "type" in d and d["type"] in Property.pTypes.values():
            if "array" in d:
                val = d["array"]
                t = d["type"]
                return PropertyArray([Property(i, t) for i in val])
        return d

    def __len__(self):
        return len(self._properties)

    def __getitem__(
        self, idx: typing.Union[slice, int]
    ) -> typing.Union[Property, typing.List[Property]]:
        return self._properties[idx]


@dataclass
class _PropertyMapFile(_JsonAble):
    """Wraps a top-level property map in a header, this is how MicroManager saves property maps to file."""

    pMap: PropertyMap

    @staticmethod
    def hook(dct: dict):
        if "format" in dct:
            if dct["format"] != "Micro-Manager Property Map" or int(dct["major_version"]) != 2:
                raise Exception("The file format does not appear to be supported.")
            return _PropertyMapFile(PropertyMap(dct["map"]))
        else:
            return dct

    def encode(self) -> dict:
        d = self.pMap.encode()
        val = (
            d["array"] if "array" in d else d["scalar"]
        )  # Putting a property map in a file breaks the usual rule so we have to do this nonsense
        return {
            "encoding": "UTF-8",
            "format": "Micro-Manager Property Map",
            "major_version": 2,
            "minor_version": 0,
            "map": val,
        }


class PropertyMap(_JsonAble):
    """Represents a propertyMap from micromanager. basically a list of properties.

    Attributes:
        properties: A list of properties
    """

    _hookRegistry = _HookReg()

    def __init__(self, properties: typing.Dict[str, Property]):
        self._propDict = properties

    def encode(self) -> dict:
        return {"type": "PROPERTY_MAP", "scalar": self._propDict}

    @staticmethod
    def hook(d: dict):
        if "type" in d and d["type"] == "PROPERTY_MAP":
            if "scalar" in d:
                return PropertyMap(d["scalar"])
        return d

    @staticmethod
    def loadFromFile(path: str) -> PropertyMap:
        with open(path) as f:
            mapFile: _PropertyMapFile = json.load(
                f, object_hook=PropertyMap._hookRegistry.getHook()
            )
        return mapFile.pMap

    def saveToFile(self, path: str):
        mapFile = _PropertyMapFile(self)
        with open(path, "w") as f:
            json.dump(mapFile, f, cls=self._Encoder, indent=2)

    class _Encoder(json.JSONEncoder):
        """Use this encoder to make use of the custom `encode` functionality of each class."""

        def default(self, obj):
            if isinstance(obj, _JsonAble):
                return obj.encode()
            elif type(obj) == np.float32:
                return float(obj)
            else:
                return json.JSONEncoder(ensure_ascii=False).default(obj)

    def __getitem__(self, key):
        return self._propDict[key]

    def __iter__(self):
        return iter(self._propDict)

    def __len__(self):
        return len(self._propDict)

    def __contains__(self, item):
        return item in self._propDict


class PropertyMapArray(_JsonAble):
    """This class is needed due to the dumb way the arrays are jsonified in Micromanager PropertyMaps."""

    def __init__(self, properties: typing.List[PropertyMap]):
        self._pmaps = properties

    def encode(self) -> dict:
        return {"type": "PROPERTY_MAP", "array": [i.encode()["scalar"] for i in self._pmaps]}

    @staticmethod
    def hook(d: dict):
        if "type" in d and d["type"] == "PROPERTY_MAP":
            if "array" in d:
                return PropertyMapArray([PropertyMap(i) for i in d["array"]])
        return d

    def __len__(self):
        return len(self._pmaps)

    def __getitem__(self, idx: typing.Union[slice, int]) -> PropertyMap:
        return self._pmaps[idx]


# Add each object type to the hook registry so it can be properly deserialized.
PropertyMap._hookRegistry.addHook(PropertyMap.hook)
PropertyMap._hookRegistry.addHook(PropertyMapArray.hook)
PropertyMap._hookRegistry.addHook(Property.hook)
PropertyMap._hookRegistry.addHook(_PropertyMapFile.hook)
PropertyMap._hookRegistry.addHook(PropertyArray.hook)


if __name__ == "__main__":
    """Test that opens a position list file, saves it to a new file and then checks that both versions
    are still identical"""
    path1 = r"PositionList.pos"
    path2 = r"PositionListOut.pos"
    p = PropertyMap.loadFromFile(path1)
    PropertyMap.saveToFile(p, path2)
    with open(path1) as f1, open(path2) as f2:
        assert f1.read() == f2.read()
