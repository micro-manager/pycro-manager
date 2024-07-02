"""
Base class for all devices that integrates with the execution engine and enables tokenization of device access.
"""
from abc import ABC, ABCMeta
from functools import wraps
from typing import Any, Dict
from weakref import WeakSet
import inspect

from pycromanager.execution_engine.base_classes.acq_events import AcquisitionEvent
from pycromanager.execution_engine.executor import ExecutionEngine
import threading

class MethodCallAcquisitionEvent(AcquisitionEvent):
    method_name: str
    args: tuple
    kwargs: Dict[str, Any]
    instance: Any

    def execute(self):
        method = getattr(self.instance, self.method_name)
        return method(*self.args, **self.kwargs)

class AttrGetAcquisitionEvent(AcquisitionEvent):
    attr_name: str
    instance: Any

    def execute(self):
        return object.__getattribute__(self.instance, self.attr_name)

class AttrSetAcquisitionEvent(AcquisitionEvent):
    attr_name: str
    value: Any
    instance: Any

    def execute(self):
        object.__setattr__(self.instance, self.attr_name, self.value)

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
            if ExecutionEngine.on_any_executor_thread():
                return attr_value(self, *args, **kwargs)
            event = MethodCallAcquisitionEvent(method_name=attr_name, args=args, kwargs=kwargs, instance=self)
            return ExecutionEngine.get_instance().submit(event).await_execution()

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


        def __getattribute__(self: 'Device', name: str) -> Any:
            if (ExecutionEngine.on_any_executor_thread() or name in ['_device_threads', '_is_internal_thread']
                    or self._is_internal_thread()):
                # we're already on the executor thread, so we can just return the attribute
                # TODO (maybe) if submit_to_free_thread is added, could allow submitting to a differente executor thread
                return object.__getattribute__(self, name)
            # TODO: it could make sense to except certain calls from being rerouted to the executor...TBD
            # elif name.startswith('_'):
            #     return object.__getattribute__(self, name)
            else:
                # if getattr(sys, 'gettrace', None) and name == 'shape':
                #     return None
                event = AttrGetAcquisitionEvent(attr_name=name, instance=self)
                return ExecutionEngine.get_instance().submit(event).await_execution()

        def __setattr__(self: 'Device', name: str, value: Any) -> None:
            if (ExecutionEngine.on_any_executor_thread() or name in ['_device_threads', '_is_internal_thread']
                     or self._is_internal_thread()):
                object.__setattr__(self, name, value)   # we're already on the executor thread, so just set it
            # TODO: it could make sense to except certain calls from being rerouted to the executor...TBD
            # elif name.startswith('_'):
            #     object.__setattr__(self, name, value)
            else:
                event = AttrSetAcquisitionEvent(attr_name=name, value=value, instance=self)
                ExecutionEngine.get_instance().submit(event).await_execution()

        new_attrs['__getattribute__'] = __getattribute__
        new_attrs['__setattr__'] = __setattr__

        return super().__new__(mcs, name, bases, new_attrs)


class Device(ABC, metaclass=DeviceMetaclass):

    _device_threads: WeakSet[threading.Thread]

    def __init__(self):
        self._device_threads = WeakSet()

    def _is_internal_thread(self):
        """
        Device calls get routed through the executor by default, but they are also allowed to have their
        own internal threads outside the executor, and rereouting these to the executor could cause deadlocks and
        confusing behavior. This method is used to determine if the current thread is one of these internal threads,
        and if so, the device will not reroute the call to the executor
        """
        current_thread = threading.current_thread()

        if current_thread in self._device_threads:
            return True

        # If not in set, perform the check
        frame = inspect.currentframe()
        try:
            while frame:
                if frame.f_locals.get('self') is self:
                    # Add the thread to the set
                    self._device_threads.add(current_thread)
                    return True
                frame = frame.f_back
        finally:
            del frame

        return False
