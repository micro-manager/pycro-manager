import pytest
from unittest.mock import MagicMock
from pycromanager.acquisition.execution_engine.base_classes.acq_events import AcquisitionEvent, DataProducing
from pycromanager.acquisition.execution_engine.executor import ExecutionEngine
from pycromanager.acquisition.execution_engine.acq_future import AcquisitionFuture
import threading
import time


def create_sync_event(start_event, finish_event):
    event = MagicMock(spec=AcquisitionEvent)
    event.num_retries_on_exception = 0
    event._uuid = None
    event.executed = False
    event.executed_time = None

    def execute():
        start_event.set()  # Signal that the execution has started
        finish_event.wait()  # Wait for the signal to finish
        event.executed = True
        event.executed_time = time.time()

    event.execute.side_effect = execute
    event._post_execution = MagicMock()
    return event


@pytest.fixture
def acquisition_event_executor():
    return ExecutionEngine(num_threads=2)


def test_submit_single_event(acquisition_event_executor):
    start_event = threading.Event()
    finish_event = threading.Event()
    event = create_sync_event(start_event, finish_event)

    future = acquisition_event_executor.submit_event(event)
    start_event.wait()  # Wait for the event to start executing
    finish_event.set()  # Signal the event to finish
    acquisition_event_executor.shutdown()

    assert event.executed
    assert isinstance(future, AcquisitionFuture)


def test_submit_multiple_events(acquisition_event_executor):
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    future1 = acquisition_event_executor.submit_event(event1)
    future2 = acquisition_event_executor.submit_event(event2)

    start_event1.wait()  # Wait for the first event to start executing
    finish_event1.set()  # Signal the first event to finish
    start_event2.wait()  # Wait for the second event to start executing
    finish_event2.set()  # Signal the second event to finish
    acquisition_event_executor.shutdown()

    assert event1.executed
    assert event2.executed
    assert isinstance(future1, AcquisitionFuture)
    assert isinstance(future2, AcquisitionFuture)


def test_event_prioritization(acquisition_event_executor):
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    start_event3 = threading.Event()
    finish_event3 = threading.Event()
    event3 = create_sync_event(start_event3, finish_event3)

    acquisition_event_executor.submit_event(event1)
    start_event1.wait()  # Wait for the first event to start executing

    acquisition_event_executor.submit_event(event2)
    acquisition_event_executor.submit_event(event3, prioritize=True)

    finish_event1.set()
    finish_event2.set()
    finish_event3.set()

    # wait till all events finished
    acquisition_event_executor.shutdown()

    assert event3.executed_time < event2.executed_time
    assert event1.executed
    assert event2.executed
    assert event3.executed


def test_use_free_thread_parallel_execution(acquisition_event_executor):
    start_event1 = threading.Event()
    finish_event1 = threading.Event()
    event1 = create_sync_event(start_event1, finish_event1)

    start_event2 = threading.Event()
    finish_event2 = threading.Event()
    event2 = create_sync_event(start_event2, finish_event2)

    acquisition_event_executor.submit(event1)
    acquisition_event_executor.submit(event2, use_free_thread=True)

    # Wait for both events to start executing
    assert start_event1.wait(timeout=5)
    assert start_event2.wait(timeout=5)

    # Ensure that both events are executing simultaneously
    assert start_event1.is_set()
    assert start_event2.is_set()

    # Signal both events to finish
    finish_event1.set()
    finish_event2.set()

    acquisition_event_executor.shutdown()

    assert event1.executed
    assert event2.executed