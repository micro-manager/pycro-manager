"""
Class that executes acquistion events across a pool of threads
"""

import threading
from collections import deque
from typing import Deque
import warnings
import traceback
from pydantic import BaseModel
import time
import uuid

from pycromanager.acquisition.new.acq_events import AcquisitionFuture
from pycromanager.acquisition.new.acq_events import AcquisitionEvent, DataProducingAcquisitionEvent


class _ExecutionThreadManager(BaseModel):
    """
    Class which manages a single thread that executes events from a queue, one at a time. Events can be added
    to either end of the queue, in order to prioritize them. The thread will stop when the shutdown method is called,
    or in the event of an unhandled exception during event execution.

    This class handles thread safety so that it is possible to check if the thread has any currently executing events
    or events in its queue with the is_free method.

    """
    _deque: Deque[AcquisitionEvent]

    def __init__(self):
        super().__init__()
        self._thread = threading.Thread(target=self._run_thread)
        self._deque = deque()
        self._shutdown_event = threading.Event()
        self._terminate_event = threading.Event()
        self._exception = None
        self._event_executing = False
        self._addition_condition = threading.Condition()
        self._thread.start()

    def join(self):
        self._thread.join()

    def _run_thread(self):
        event = None
        while True:
            if self._terminate_event.is_set():
                return
            if self._shutdown_event.is_set() and self.is_free():
                return
            # Event retrieval loop
            while event is None:
                with self._addition_condition:
                    if not self._deque:
                        # wait until something is in the queue
                        self._addition_condition.wait()
                    if self._terminate_event.is_set():
                        return
                    if self._shutdown_event.is_set() and not self._deque:
                        # awoken by a shutdown event and the queue is empty
                        return
                    event = self._deque.popleft()
                    if not hasattr(event, 'num_retries_on_exception'):
                        warnings.warn("Event does not have num_retries_on_exception attribute, setting to 0")
                        event.num_retries_on_exception = 0
                    num_retries = event.num_retries_on_exception
                    self._event_executing = True

            # Event execution loop
            while True:
                try:
                    event.execute()
                    event._post_execution() # notify futures
                    with self._addition_condition:
                        self._event_executing = False
                    break
                except Exception as e:
                    if num_retries > 0:
                        if self._terminate_event.is_set():
                            return
                        num_retries -= 1
                        warnings.warn(f"Exception during event execution, retrying {num_retries} more times")
                        traceback.print_exc()
                    else:
                        event._exception = e
                        event._post_execution() # notify futures
                        with self._addition_condition:
                            self._event_executing = False
                        raise e # re-raise the exception to stop the thread
            event = None

    def is_free(self):
        """
        return true if an event is not currently being executed and the queue is empty
        """
        with self._addition_condition:
            return not self._event_executing and not self._deque and not \
                    self._terminate_event.is_set() and not self._shutdown_event.is_set()

    def submit_event(self, event, prioritize=False):
        """
        Submit an event for execution on this thread. If prioritize is True, the event will be executed before any other
        events in the queue.

        Returns:
            uuid.UUID: A unique identifier for the event, which can be used to check if the event has been executed
        """
        if event._uuid is not None:
            warnings.warn("Event has already been executed. Re-executing may lead to unexpected behavior")
        event._uuid = uuid.uuid1()
        with self._addition_condition:
            if self._shutdown_event.is_set() or self._terminate_event.is_set():
                raise RuntimeError("Cannot submit event to a thread that has been shutdown")
            if prioritize:
                self._deque.appendleft(event)
            else:
                self._deque.append(event)
            self._addition_condition.notify_all()
        return event._uuid


    def terminate(self):
        """
        Stop the thread immediately, without waiting for the current event to finish
        """
        with self._addition_condition:
            self._terminate_event.set()
            self._shutdown_event.set()
            self._addition_condition.notify_all()
        self._thread.join()
    def shutdown(self):
        """
        Stop the thread and wait for it to finish
        """
        with self._addition_condition:
            self._shutdown_event.set()
            self._addition_condition.notify_all()
        self._thread.join()


class AcquisitionEventExecutor:
    def __init__(self, num_threads=1):
        self._threads = []
        for _ in range(num_threads):
            self._start_new_thread()

    def _start_new_thread(self):
        self._threads.append(_ExecutionThreadManager())

    def submit_event(self, event, prioritize=False, use_free_thread=False, data_output_queue=None):
        """
        Submit an event for execution on one of the active threads. By default, all events will be executed
        on a single thread in the order they were submitted. This is the simplest way to prevent concurrency issues
        with hardware devices. With thread-safe code, events can be parallelized by submitting them to different threads
        using the use_free_thread argument. By default, events will be executed in the order they were submitted, but
        if prioritize is set to True, the event will be executed before any other events in the queue on its thread.

        Parameters:
            event (AcquisitionEvent): The event to execute
            prioritize (bool): If True, the event will be executed before any other events queued on its execution thread
            use_free_thread (bool): If True, the event will be executed on a thread that is not currently executing
                 and has nothing in its queue, creating a new thread if necessary. This is needed, for example, when using
                 an event to cancel or stop another event that is awaiting a stop signal to be rewritten to the state. If
                 this is set to False (the default), the event will be executed on the primary thread.
            data_output_queue (DataOutputQueue): The queue to put data into if the event produces data
        """
        # check that DataProducingAcquisitionEvents have a data output queue
        if isinstance(event, DataProducingAcquisitionEvent) and data_output_queue is None:
            raise ValueError("DataProducingAcquisitionEvent must have a data_output_queue argument")

        future = AcquisitionFuture(event)
        event._future = future
        if use_free_thread:
            for thread in self._threads:
                if thread.is_free():
                    thread.submit_event(event)
                    break
            self._start_new_thread()
            self._threads[-1].submit_event(event)
        else:
            self._threads[0].submit_event(event, prioritize=prioritize)

        return future



    def shutdown(self):
        """
        Stop all threads and wait for them to finish
        """
        for thread in self._threads:
            thread.shutdown()
        for thread in self._threads:
            thread.join()