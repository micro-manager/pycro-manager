from docstring_inheritance import NumpyDocstringInheritanceMeta
import queue
from pycromanager.acquisition.acq_eng_py.main.acquisition_py import Acquisition as pymmcore_Acquisition
from pycromanager.acquisition.acq_eng_py.RAMStorage import RAMDataStorage
import time
from pycromanager.acquisition.acquisition_superclass import _validate_acq_events, PycromanagerAcquisition
from pycromanager.acquisition.acq_eng_py.main.acquisition_event import AcquisitionEvent
import threading

class PythonBackendAcquisition(PycromanagerAcquisition, metaclass=NumpyDocstringInheritanceMeta):
    """
    Pycro-Manager acquisition that uses a Python runtime backend. Unlike the Java backend,
    Python-backed acquisitions currently do not automatically write data to disk. Instead, by default,
    they store data in RAM which can be queried with the Dataset class. If instead you want to
    implement your own data storage, you can pass an image_process_fn which diverts the data to
    a custom endpoint.
    """

    def __init__(
        self,
        store_data_in_memory: bool=True,
        image_process_fn: callable=None,
        pre_hardware_hook_fn: callable=None,
        post_hardware_hook_fn: callable=None,
        post_camera_hook_fn: callable=None,
        show_display: bool=True,
        napari_viewer=None,
        image_saved_fn: callable=None,
        debug: int=False,
    ):
        self._debug = debug
        if not store_data_in_memory and image_process_fn is None:
            raise ValueError('Must either store data in memory or provide an image_process_fn')
        self._dataset = RAMDataStorage() if store_data_in_memory else None
        self._finished = False
        self._exception = None
        self._napari_viewer = None
        self._notification_queue = queue.Queue(30)
        self._create_event_queue()

        # create a thread that submits events
        # events can be added to the queue through image processors, hooks, or the acquire method
        def submit_events():
            while True:
                event_or_events = self._event_queue.get()
                if event_or_events is None:
                    self._acq.finish()
                    while not self._acq.are_events_finished():
                        time.sleep(0.001)
                    break
                _validate_acq_events(event_or_events)
                if isinstance(event_or_events, dict):
                    event_or_events = [event_or_events]
                # convert to objects
                event_or_events = [AcquisitionEvent.from_json(event, self._acq) for event in event_or_events]
                self._acq.submit_event_iterator(iter(event_or_events))
        self._event_thread = threading.Thread(target=submit_events)
        self._event_thread.start()

        # TODO: notification handling

        self._acq = pymmcore_Acquisition(self._dataset)

        # add hooks and image processor
        # TODO hooks and processor need to be wrapped appropriately
        # if pre_hardware_hook_fn is not None:
        #     self._acq.add_hook(pre_hardware_hook_fn, self._acq.BEFORE_HARDWARE_HOOK)
        # if post_hardware_hook_fn is not None:
        #     self._acq.add_hook(post_hardware_hook_fn, self._acq.AFTER_HARDWARE_HOOK)
        # if post_camera_hook_fn is not None:
        #     self._acq.add_hook(post_camera_hook_fn, self._acq.AFTER_CAMERA_HOOK)
        # if event_generation_hook_fn is not None:
        #     self._acq.add_hook(event_generation_hook_fn, self._acq.EVENT_GENERATION_HOOK)
        # if image_process_fn is not None:
        #     raise NotImplementedError('image_process_fn not yet implemented')
            # need to make a dedicated thread for it
            # self._acq.add_image_processor(image_process_fn)


        if show_display:
            # using napari viewer
            try:
                import napari
            except:
                raise Exception('Napari must be installed in order to use this feature')
            from pycromanager.napari_util import start_napari_signalling
            assert isinstance(napari_viewer, napari.Viewer), 'napari_viewer must be an instance of napari.Viewer'
            self._napari_viewer = napari_viewer
            start_napari_signalling(self._napari_viewer, self.get_dataset())


    ########  Public API ###########
    def get_dataset(self):
        return self._dataset

    def await_completion(self):
        """Wait for acquisition to finish and resources to be cleaned up"""
        while not self._acq.are_events_finished() or (
                self._acq.get_data_sink() is not None and not self._acq.get_data_sink().is_finished()):
            time.sleep(1 if self._debug else 0.05)
            self._check_for_exceptions()
        self._event_thread.join()

        # TODO: shut down notifications?
        # self._acq_notification_thread.join()
        # self._remote_notification_handler.notification_handling_complete()

        self._acq = None
        self._finished = True

    def get_viewer(self):
        """
        Return a reference to the current viewer, if the show_display argument
        was set to True. The returned object is either an instance of NDViewer or napari.Viewer()
        """
        return self._napari_viewer

    ########  Context manager (i.e. "with Acquisition...") ###########
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mark_finished()
        # now wait on it to finish
        self.await_completion()

    def _check_for_exceptions(self):
        """
        Check for exceptions on the python side (i.e. hooks and processors)
        or on the Java side (i.e. hardware control)
        """
        # these will throw exceptions
        self._acq.check_for_exceptions()
        if self._exception is not None:
            raise self._exception

