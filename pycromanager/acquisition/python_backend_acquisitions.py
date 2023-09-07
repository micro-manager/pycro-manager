from docstring_inheritance import NumpyDocstringInheritanceMeta
from pycromanager.acquisition.acq_eng_py.main.AcqEngPy_Acquisition import Acquisition as pymmcore_Acquisition
from pycromanager.acquisition.RAMStorage import RAMDataStorage
from pycromanager.acquisition.acquisition_superclass import _validate_acq_events, Acquisition
from pycromanager.acquisition.acq_eng_py.main.acquisition_event import AcquisitionEvent
from pycromanager.acq_future import AcqNotification
import threading
from inspect import signature


class PythonBackendAcquisition(Acquisition, metaclass=NumpyDocstringInheritanceMeta):
    """
    Pycro-Manager acquisition that uses a Python runtime backend. Unlike the Java backend,
    Python-backed acquisitions currently do not automatically write data to disk. Instead, by default,
    they store data in RAM which can be queried with the Dataset class. If instead you want to
    implement your own data storage, you can pass an image_process_fn which diverts the data to
    a custom endpoint.
    """

    def __init__(
        self,
        directory: str=None,
        name: str='default_acq_name',
        image_process_fn: callable=None,
        event_generation_hook_fn: callable = None,
        pre_hardware_hook_fn: callable=None,
        post_hardware_hook_fn: callable=None,
        post_camera_hook_fn: callable=None,
        notification_callback_fn: callable=None,
        napari_viewer=None,
        image_saved_fn: callable=None,
        debug: int=False,
    ):
        # Get a dict of all named argument values (or default values when nothing provided)
        arg_names = [k for k in signature(PythonBackendAcquisition.__init__).parameters.keys() if k != 'self']
        l = locals()
        named_args = {arg_name: (l[arg_name] if arg_name in l else
                                     dict(signature(PythonBackendAcquisition.__init__).parameters.items())[arg_name].default)
                                     for arg_name in arg_names }
        super().__init__(**named_args)
        if directory is not None:
            raise NotImplementedError('Saving to disk is not yet implemented for the python backend. ')
        self._dataset = RAMDataStorage()
        self._finished = False
        self._notifications_finished = False
        self._create_event_queue()

        self._process_fn = image_process_fn
        self._image_processor = ImageProcessor(self) if image_process_fn is not None else None


        # create a thread that submits events
        # events can be added to the queue through image processors, hooks, or the acquire method
        def submit_events():
            while True:
                event_or_events = self._event_queue.get()
                if event_or_events is None:
                    self._acq.finish()
                    self._acq.block_until_events_finished()
                    break
                _validate_acq_events(event_or_events)
                if isinstance(event_or_events, dict):
                    event_or_events = [event_or_events]
                # convert to objects
                event_or_events = [AcquisitionEvent.from_json(event, self._acq) for event in event_or_events]
                self._acq.submit_event_iterator(iter(event_or_events))
        self._event_thread = threading.Thread(target=submit_events)
        self._event_thread.start()

        self._acq = pymmcore_Acquisition(self._dataset)

        # receive notifications from the acquisition engine. Unlike the java_backend analog
        # of this, the python backend does not have a separate thread for notifications because
        # it can just use the one in AcqEngPy
        def post_notification(notification):
            self._notification_queue.put(notification)
            # these are processed seperately to handle image saved callback
            if AcqNotification.is_image_saved_notification(notification):
                self._image_notification_queue.put(notification)

        self._acq.add_acq_notification_listener(NotificationListener(post_notification))

        self._notification_dispatch_thread = self._start_notification_dispatcher(notification_callback_fn)

        # add hooks and image processor
        if pre_hardware_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(pre_hardware_hook_fn),self._acq.BEFORE_HARDWARE_HOOK)
        if post_hardware_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(post_hardware_hook_fn),self._acq.AFTER_HARDWARE_HOOK)
        if post_camera_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(post_camera_hook_fn),self._acq.AFTER_CAMERA_HOOK)
        if event_generation_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(event_generation_hook_fn),self._acq.EVENT_GENERATION_HOOK)
        if self._image_processor is not None:
            self._acq.add_image_processor(self._image_processor)


        if napari_viewer is not None:
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
            self._check_for_exceptions()
            self._acq.block_until_events_finished(0.05)
            if self._acq.get_data_sink() is not None:
                self._acq.get_data_sink().block_until_finished(0.05)
            self._check_for_exceptions()
        self._event_thread.join()
        self._notification_dispatch_thread.join()

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

    def _are_acquisition_notifications_finished(self):
        """
        Called by the storage to check if all notifications have been processed
        """
        return self._notifications_finished

class ImageProcessor:
    """
    This is the equivalent of RemoteImageProcessor in the Java version.
    It runs its own thread, polls the input queue for images, calls
    the process function, and puts the result in the output queue.
    """


    def __init__(self, pycromanager_acq):
        self._pycromanager_acq = pycromanager_acq

    def set_acq_and_queues(self, acq, input, output):
        self.input_queue = input
        self.output_queue = output
        self._acq = acq
        self._process_thread = threading.Thread(target=self._process)
        self._process_thread.start()

    def _process(self):
        while True:
            # wait for an image to arrive
            tagged_image = self.input_queue.get()
            if tagged_image.tags is None and tagged_image.pix is None:
                # this is a signal to stop
                self.output_queue.put(tagged_image)
                break
            process_fn_result = self._pycromanager_acq._call_image_process_fn(tagged_image.tags, tagged_image.pix)
            if process_fn_result is not None:
                self.output_queue.put(process_fn_result)
            # otherwise the image processor intercepted the image and nothing to do here

class AcquisitionHook:
    """
    Lightweight wrapper to convert function pointers to AcqEng hooks
    """

    def __init__(self, hook_fn):
        self._hook_fn = hook_fn

    def run(self, event):
        self._hook_fn(event)

    def close(self):
        pass # nothing to do here

class NotificationListener:
    """
    Lightweight wrapper to convert function pointers to AcqEng notification listeners
    """

    def __init__(self, notification_fn):
        self._notification_fn = notification_fn

    def post_notification(self, notification):
        self._notification_fn(notification)