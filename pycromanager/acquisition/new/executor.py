"""
Class that executes acquistion events across a pool of threads
"""
import threading
from collections import deque
from typing import Deque
import warnings
import traceback
from pydantic import BaseModel
import uuid
from typing import Union, Iterable

from pycromanager.acquisition.new.acq_future import AcquisitionFuture
from pycromanager.acquisition.new.base_classes.acq_events import AcquisitionEvent, DataProducingAcquisitionEvent
from pycromanager.acquisition.new.data_handler import DataHandler


class ExecutionEngine:

    _instance = None

    def __init__(self, num_threads=1):
        self._threads = []
        for _ in range(num_threads):
            self._start_new_thread()
        self._instance = self

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            raise RuntimeError("ExecutionEngine has not been initialized")
        return cls._instance

    def _start_new_thread(self):
        self._threads.append(_ExecutionThreadManager())

    def submit(self, event_or_events: Union[AcquisitionEvent, Iterable[AcquisitionEvent]],
               transpile: bool = True, prioritize: bool = False, use_free_thread: bool = False,
               data_handler: DataHandler = None) -> Union[AcquisitionFuture, Iterable[AcquisitionFuture]]:
        """
        Submit one or more acquisition events for execution.

        This method handles the submission of acquisition events to be executed on active threads. It provides
        options for event prioritization, thread allocation, and performance optimization.

        Execution Behavior:
        - By default, all events are executed on a single thread in submission order to prevent concurrency issues.
        - Events can be parallelized across different threads using the 'use_free_thread' parameter.
        - Priority execution can be requested using the 'prioritize' parameter.

        Parameters:
        ----------
        event_or_events : Union[AcquisitionEvent, Iterable[AcquisitionEvent]]
            A single AcquisitionEvent or an iterable of AcquisitionEvents to be submitted.

        transpile : bool, optional (default=True)
            If True and multiple events are submitted, attempt to optimize them for better performance.
            This may result in events being combined or reorganized.

        prioritize : bool, optional (default=False)
            If True, execute the event(s) before any others in the queue on its assigned thread.
            Useful for system-wide changes affecting other events, like hardware adjustments.

        use_free_thread : bool, optional (default=False)
            If True, execute the event(s) on an available thread with an empty queue, creating a new one if necessary.
            Useful for operations like cancelling or stopping events awaiting signals.
            If False, execute on the primary thread.

        data_handler : DataHandler, optional (default=None)
            Object to handle data and metadata produced by DataProducingAcquisitionEvents.

        Returns:
        -------
        Union[AcquisitionFuture, Iterable[AcquisitionFuture]]
            For a single event: returns a single AcquisitionFuture.
            For multiple events: returns an Iterable of AcquisitionFutures.
            Note: The number of returned futures may differ from the input if transpilation occurs.

        Notes:
        -----
        - Transpilation may optimize multiple events, potentially altering their number or structure.
        - Use 'prioritize' for critical system changes that should occur before other queued events.
        - 'use_free_thread' is essential for operations that need to run independently, like cancellation events.
        """
        if isinstance(event_or_events, AcquisitionEvent):
            event_or_events = [event_or_events]

        if transpile:
            # TODO: transpile events
            pass

        futures = tuple(self._submit_single_event(event, use_free_thread, prioritize)
                   for event in event_or_events)
        if len(futures) == 1:
            return futures[0]
        return futures

    def _submit_single_event(self, event: AcquisitionEvent, use_free_thread: bool = False, prioritize: bool = False):
        """
        Submit a single event for execution
        """
        future = AcquisitionFuture(event=event)
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
        Stop all threads managed by this executor and wait for them to finish
        """
        for thread in self._threads:
            thread.shutdown()
        for thread in self._threads:
            thread.join()


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
            if self._shutdown_event.is_set() and not self._deque:
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
                        traceback.print_exc()
                        event._post_execution(e) # notify futures
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
        """
        with self._addition_condition:
            if self._shutdown_event.is_set() or self._terminate_event.is_set():
                raise RuntimeError("Cannot submit event to a thread that has been shutdown")
            if prioritize:
                self._deque.appendleft(event)
            else:
                self._deque.append(event)
            self._addition_condition.notify_all()


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

