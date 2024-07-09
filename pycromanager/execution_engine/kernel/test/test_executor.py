"""
Unit tests for the ExecutionEngine and Device classes.
Ensures rerouting of method calls to the ExecutionEngine and proper handling of internal threads.
"""

import pytest
from unittest.mock import MagicMock
from pycromanager.execution_engine.kernel.acq_event_base import AcquisitionEvent
from pycromanager.execution_engine.kernel.acq_future import AcquisitionFuture
from pycromanager.execution_engine.kernel.device import Device
import time


@pytest.fixture(scope="module")
def execution_engine():
    engine = ExecutionEngine(num_threads=2)
    yield engine
    engine.shutdown()


#############################################################################################
# Tests for automated rerouting of method calls to the ExecutionEngine to executor threads
#############################################################################################
class MockDevice(Device):
    def __init__(self):
        self._test_attribute = None

    def test_method(self):
        assert ExecutionEngine.on_any_executor_thread()
        assert threading.current_thread().execution_engine_thread
        return True

    def set_test_attribute(self, value):
        assert ExecutionEngine.on_any_executor_thread()
        assert threading.current_thread().execution_engine_thread
        self._test_attribute = value

    def get_test_attribute(self):
        assert ExecutionEngine.on_any_executor_thread()
        assert threading.current_thread().execution_engine_thread
        return self._test_attribute

def test_device_method_execution(execution_engine):
    mock_device = MockDevice()

    result = mock_device.test_method()
    assert result is True

def test_device_attribute_setting(execution_engine):
    mock_device = MockDevice()

    mock_device.set_test_attribute("test_value")
    result = mock_device.get_test_attribute()
    assert result == "test_value"

def test_device_attribute_direct_setting(execution_engine):
    mock_device = MockDevice()

    mock_device.direct_set_attribute = "direct_test_value"
    assert mock_device.direct_set_attribute == "direct_test_value"

def test_multiple_method_calls(execution_engine):
    mock_device = MockDevice()

    result1 = mock_device.test_method()
    mock_device.set_test_attribute("test_value")
    result2 = mock_device.get_test_attribute()

    assert result1 is True
    assert result2 == "test_value"


#######################################################
# Tests for internal threads in Devices
#######################################################

from concurrent.futures import ThreadPoolExecutor
from pycromanager.execution_engine.kernel.executor import ExecutionEngine
from pycromanager.execution_engine.kernel.device import Device
import threading


class ThreadCreatingDevice(Device):
    def __init__(self):
        self.test_attribute = None
        self._internal_thread_result = None
        self._nested_thread_result = None

    def create_internal_thread(self):
        def internal_thread_func():
            # This should not be on an executor thread
            assert not ExecutionEngine.on_any_executor_thread()
            assert not getattr(threading.current_thread(), 'execution_engine_thread', False)
            self.test_attribute = "set_by_internal_thread"

        thread = threading.Thread(target=internal_thread_func)
        thread.start()
        thread.join()

    def create_nested_thread(self):
        def nested_thread_func():
            # This should not be on an executor thread
            assert not ExecutionEngine.on_any_executor_thread()
            assert not getattr(threading.current_thread(), 'execution_engine_thread', False)
            self.test_attribute = "set_by_nested_thread"

        def internal_thread_func():
            thread = threading.Thread(target=nested_thread_func)
            thread.start()
            thread.join()

        thread = threading.Thread(target=internal_thread_func)
        thread.start()
        thread.join()


    def use_threadpool_executor(self):
        def threadpool_func():
            # This should not be on an executor thread
            assert not ExecutionEngine.on_any_executor_thread()
            assert not getattr(threading.current_thread(), 'execution_engine_thread', False)
            self.test_attribute = "set_by_threadpool"

        with ThreadPoolExecutor() as executor:
            executor.submit(threadpool_func)


def test_device_internal_thread(execution_engine):
    """
    Test that a thread created internally by a device is not treated as an executor thread.

    This integration_tests verifies that when a device creates its own internal thread, the code running
    on that thread is not identified as being on an executor thread. It does this by:
    1. Creating a ThreadCreatingDevice instance
    2. Calling a method that spawns an internal thread
    3. Checking that the internal thread successfully set an attribute, indicating that
       it ran without raising any assertions about being on an executor thread
    """
    print('integration_tests started')
    device = ThreadCreatingDevice()
    print('getting ready to create internal thread')
    t = device.create_internal_thread()
    # t.join()

    # while device.test_attribute is None:
    #     time.sleep(0.1)
    assert device.test_attribute == "set_by_internal_thread"


def test_device_nested_thread(execution_engine):
    """
    Test that a nested thread (a thread created by another thread within the device)
    is not treated as an executor thread.

    This integration_tests ensures that even in a nested thread scenario, the code is not identified
    as running on an executor thread. It does this by:
    1. Creating a ThreadCreatingDevice instance
    2. Calling a method that spawns an internal thread, which in turn spawns another thread
    3. Checking that the nested thread successfully set an attribute, indicating that
       it ran without raising any assertions about being on an executor thread
    """
    device = ThreadCreatingDevice()
    device.create_nested_thread()
    while device.test_attribute is None:
        time.sleep(0.1)
    assert device.test_attribute == "set_by_nested_thread"


def test_device_threadpool_executor(execution_engine):
    """
    Test that a thread created by ThreadPoolExecutor within a device method
    is not treated as an executor thread.

    This integration_tests verifies that when using Python's ThreadPoolExecutor to create a thread
    within a device method, the code running in this thread is not identified as being
    on an executor thread. It does this by:
    1. Creating a ThreadCreatingDevice instance
    2. Calling a method that uses ThreadPoolExecutor to run a function
    3. Checking that the function successfully set an attribute, indicating that
       it ran without raising any assertions about being on an executor thread
    """
    device = ThreadCreatingDevice()
    device.use_threadpool_executor()
    while device.test_attribute is None:
        time.sleep(0.1)
    assert device.test_attribute == "set_by_threadpool"


#######################################################
# Tests for other ExecutionEngine functionalities
#######################################################
def create_sync_event(start_event, finish_event):
    event = MagicMock(spec=AcquisitionEvent)
    event.num_retries_on_exception = 0
    event.executed = False
    event.executed_time = None
    event.execute_count = 0

    def execute():
        start_event.set()  # Signal that the execution has started
        finish_event.wait()  # Wait for the signal to finish
        event.executed_time = time.time()
        event.execute_count += 1
        event.executed = True

    event.execute.side_effect = execute
    event.is_finished.side_effect = lambda: event.executed
    event._post_execution = MagicMock()
    return event


def test_submit_single_event(execution_engine):
    """
    Test submitting a single event to the ExecutionEngine.
    Verifies that the event is executed and returns an AcquisitionFuture.
    """
    start_event = threading.Event()
    finish_event = threading.Event()
    event = create_sync_event(start_event, finish_event)

    future = execution_engine.submit(event)
    start_event.wait()  # Wait for the event to start executing
    finish_event.set()  # Signal the event to finish

    while not event.executed:
        time.sleep(0.1)

    assert event.executed
    assert isinstance(future, AcquisitionFuture)


def test_submit_multiple_events(execution_engine):
    """
    Test submitting multiple event_implementations to the ExecutionEngine.
    Verifies that all event_implementations are executed and return AcquisitionFutures.
    """
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    future1 = execution_engine.submit(event1)
    future2 = execution_engine.submit(event2)

    start_event1.wait()  # Wait for the first event to start executing
    finish_event1.set()  # Signal the first event to finish
    start_event2.wait()  # Wait for the second event to start executing
    finish_event2.set()  # Signal the second event to finish

    while not event1.executed or not event2.executed:
        time.sleep(0.1)

    assert event1.executed
    assert event2.executed
    assert isinstance(future1, AcquisitionFuture)
    assert isinstance(future2, AcquisitionFuture)


def test_event_prioritization(execution_engine):
    """
    Test event prioritization in the ExecutionEngine.
    Verifies that prioritized event_implementations are executed before non-prioritized event_implementations.
    """
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    start_event3 = threading.Event()
    finish_event3 = threading.Event()
    event3 = create_sync_event(start_event3, finish_event3)

    execution_engine.submit(event1)
    start_event1.wait()  # Wait for the first event to start executing

    execution_engine.submit(event2)
    execution_engine.submit(event3, prioritize=True)

    finish_event1.set()
    finish_event2.set()
    finish_event3.set()

    while not event1.executed or not event2.executed or not event3.executed:
        time.sleep(0.1)

    assert event3.executed_time < event2.executed_time
    assert event1.executed
    assert event2.executed
    assert event3.executed


def test_use_free_thread_parallel_execution(execution_engine):
    """
    Test parallel execution using free threads in the ExecutionEngine.
    Verifies that event_implementations submitted with use_free_thread=True can execute in parallel.
    """
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    execution_engine.submit(event1)
    execution_engine.submit(event2, use_free_thread=True)

    # Wait for both event_implementations to start executing
    assert start_event1.wait(timeout=5)
    assert start_event2.wait(timeout=5)

    # Ensure that both event_implementations are executing simultaneously
    assert start_event1.is_set()
    assert start_event2.is_set()

    # Signal both event_implementations to finish
    finish_event1.set()
    finish_event2.set()

    while not event1.executed or not event2.executed:
        time.sleep(0.1)

    assert event1.executed
    assert event2.executed


def test_single_execution_with_free_thread(execution_engine):
    """
    Test that each event is executed only once, even when using use_free_thread=True.
    Verifies that event_implementations are not executed multiple times regardless of submission method.
    """
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    execution_engine.submit(event1)
    execution_engine.submit(event2, use_free_thread=True)

    # Wait for both event_implementations to start executing
    assert start_event1.wait(timeout=5)
    assert start_event2.wait(timeout=5)

    # Signal both event_implementations to finish
    finish_event1.set()
    finish_event2.set()

    while not event1.executed or not event2.executed:
        time.sleep(0.1)

    assert event1.executed
    assert event2.executed
    assert event1.execute_count == 1
    assert event2.execute_count == 1