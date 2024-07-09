"""
Base class for all device_implementations that integrates with the execution engine and enables tokenization of device access.
"""
from abc import ABC, ABCMeta
from functools import wraps
from typing import Any, Dict, Callable
from weakref import WeakSet

from pycromanager.execution_engine.kernel.acq_event_base import AcquisitionEvent
from pycromanager.execution_engine.kernel.executor import ExecutionEngine
import threading


# All threads that were created by code running on an executor thread, or created by threads that were created by
# code running on an executor thread etc. Don't want to auto-reroute these to the executor because this might have
# unintended consequences. So they need to be tracked and not rerouted
_within_executor_threads = WeakSet()

def thread_start_hook(thread):
    print('thread start hook')
    if ExecutionEngine.on_any_executor_thread() or threading.current_thread() in _within_executor_threads:
        _within_executor_threads.add(thread)
        print(f"Thread started by executor: {thread}")
        # traceback.print_stack()
    else:
        print(f"Thread started by non-executor code: {thread}")

# Monkey patch the threading module so we can monitor the creation of new threads
_original_thread_start = threading.Thread.start

# Define a new start method that adds the hook
def _thread_start(self, *args, **kwargs):
    try:
        thread_start_hook(self)
        _original_thread_start(self, *args, **kwargs)
    except Exception as e:
        print(f"Error in thread start hook: {e}")
        # traceback.print_exc()

# Replace the original start method with the new one
threading.Thread.start = _thread_start


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
    method: Callable

    def execute(self):
        return self.method(self.instance, self.attr_name)

class AttrSetAcquisitionEvent(AcquisitionEvent):
    attr_name: str
    value: Any
    instance: Any
    method: Callable

    def execute(self):
        self.method(self.instance, self.attr_name, self.value)


class DeviceMetaclass(ABCMeta):
    """
    Metaclass for device_implementations that wraps all methods and attributes in the device class to add the ability to
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

    @staticmethod
    def find_in_bases(bases, method_name):
        for base in bases:
            if hasattr(base, method_name):
                return getattr(base, method_name)
        return None

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

        def is_debugger_thread():
            # This is a heuristic and may need adjustment based on the debugger used.
            debugger_thread_names = ["pydevd", "Debugger"]  # Common names for debugger threads
            current_thread = threading.current_thread()
            # Check if current thread name contains any known debugger thread names
            return any(name in current_thread.name for name in debugger_thread_names)


        original_setattr = attrs.get('__setattr__') or mcs.find_in_bases(bases, '__setattr__') or object.__setattr__
        original_getattribute = attrs.get('__getattribute__') or mcs.find_in_bases(bases, '__getattribute__') or object.__getattribute__


        def __getattribute__(self: 'Device', name: str) -> Any:
            if is_debugger_thread():
                return original_getattribute(self, name)
            if ExecutionEngine.on_any_executor_thread():
                # already on the executor thread, so proceed as normal
                return original_getattribute(self, name)
            elif threading.current_thread() in _within_executor_threads:
                return original_getattribute(self, name)
            else:
                # This was from a pycharm debugger issue that mysteriously disappeared
                # if getattr(sys, 'gettrace', None) and name == 'shape':
                #     return None
                # TODO: it could make sense to except certain calls from being rerouted to the executor...TBD
                event = AttrGetAcquisitionEvent(attr_name=name, instance=self, method=original_getattribute)
                return ExecutionEngine.get_instance().submit(event).await_execution()

        def __setattr__(self: 'Device', name: str, value: Any) -> None:
            # These methods don't need to be on the executor because they have nothing to do with hardware
            if is_debugger_thread():
                original_setattr(self, name, value)
            elif ExecutionEngine.on_any_executor_thread():
                original_setattr(self, name, value)  # we're already on the executor thread, so just set it
            elif threading.current_thread() in _within_executor_threads:
                original_setattr(self, name, value)
            else:

                # TODO: it could make sense to except certain calls from being rerouted to the executor...TBD
                event = AttrSetAcquisitionEvent(attr_name=name, value=value, instance=self, method=original_setattr)
                ExecutionEngine.get_instance().submit(event).await_execution()

        new_attrs['__getattribute__'] = __getattribute__
        new_attrs['__setattr__'] = __setattr__

        # Pycharm debugger is always looking for shape. this is a hack to make it not throw exceptions
        new_attrs['shape'] = None

        return super().__new__(mcs, name, bases, new_attrs)

class Device(ABC, metaclass=DeviceMetaclass):

    pass
    # def __str__(self):
    #     class_specific_attrs = getattr(self, '_event_attrs', [])
    #     attrs = ', '.join(f"{getattr(self, attr)}" for attr in class_specific_attrs if hasattr(self, attr))
    #     return f"{self.__class__.__name__}({attrs})"
