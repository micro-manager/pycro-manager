"""
Base class for all devices that integrates with the execution engine and enables tokenization of device access.
"""
from abc import ABC, ABCMeta
from functools import wraps
from typing import Any, Dict

from pycromanager.acquisition.new.base_classes.acq_events import AcquisitionEvent
from pycromanager.acquisition.new.executor import ExecutionEngine


class MethodCallAcquisitionEvent(AcquisitionEvent):
    method_name: str
    args: tuple
    kwargs: Dict[str, Any]
    instance: Any

    def execute(self):
        method = getattr(self.instance, self.method_name)
        return method(*self.args, **self.kwargs)

class AttrAccessAcquisitionEvent(AcquisitionEvent):
    attr_name: str
    instance: Any

    def execute(self):
        return getattr(self.instance, self.attr_name)

class AttrSetAcquisitionEvent(AcquisitionEvent):
    attr_name: str
    value: Any
    instance: Any

    def execute(self):
        setattr(self.instance, self.attr_name, self.value)


class DeviceMetaclass(ABCMeta):
    """
    Metaclass for devices that wraps all methods and attributes in the device class to add the ability to
    control their execution and access. This has two purposes:

    1) Add the ability to record all method calls and attribute accesses for tokenization
    2) Add the ability to make all methods and attributes thread-safe by putting them on the Executor
    """
    @staticmethod
    def wrap_for_executor(attr_name, attr_value):
        if hasattr(attr_value, '_wrapped_for_executor'):
            return attr_value

        @wraps(attr_value)
        def wrapper(self: 'Device', *args: Any, **kwargs: Any) -> Any:
            event = MethodCallAcquisitionEvent(method_name=attr_name, args=args, kwargs=kwargs, instance=self)
            return self._executor.submit(event).await_execution()

        wrapper._wrapped_for_executor = True
        return wrapper


    def __new__(mcs, name: str, bases: tuple, attrs: dict) -> Any:
        new_attrs = {}
        for attr_name, attr_value in attrs.items():
            if not attr_name.startswith('_'):
                if callable(attr_value):
                    new_attrs[attr_name] = mcs.wrap_for_executor(attr_name, attr_value)
                else:
                    pass
            else:
                new_attrs[attr_name] = attr_value

        def __getattr__(self: 'Device', name: str) -> Any:
            if name.startswith('__'):
                return super().__getattribute__(name)

            event = AttrAccessAcquisitionEvent(
                attr_name=name,
                instance=self
            )
            return self._executor.submit(event).await_execution()

        def __setattr__(self: 'Device', name: str, value: Any) -> None:
            if name.startswith('_'):
                object.__setattr__(self, name, value)
            else:
                event = AttrSetAcquisitionEvent(
                    attr_name=name,
                    value=value,
                    instance=self
                )
                self._executor.submit(event).await_execution()

        new_attrs['__getattr__'] = __getattr__
        new_attrs['__setattr__'] = __setattr__

        return super().__new__(mcs, name, bases, new_attrs)


class Device(ABC, metaclass=DeviceMetaclass):
    def __init__(self):
        self._executor: ExecutionEngine = ExecutionEngine.get_instance()
