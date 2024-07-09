import warnings
from docstring_inheritance import NumpyDocstringInheritanceMeta
from pycromanager.acquisition.acquisition_superclass import _validate_acq_events, Acquisition
# from pycromanager.acquisition.execution_engine.acq_events import AcquisitionEvent
#TODO:
AcquisitionEvent = None
from pycromanager.acquisition.acq_eng_py.main.acq_eng_metadata import AcqEngMetadata
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification
from pycromanager.acquisition.acq_eng_py.internal.notification_handler import NotificationHandler
from pycromanager.acquisition.acq_eng_py.internal.engine import Engine
import threading
from inspect import signature
import traceback
import queue

from ndstorage.ndram_dataset import NDRAMDataset
from ndstorage.ndtiff_dataset import NDTiffDataset

from pycromanager.acquisition.acq_eng_py.internal.hooks import EVENT_GENERATION_HOOK, \
    BEFORE_HARDWARE_HOOK, BEFORE_Z_DRIVE_HOOK, AFTER_HARDWARE_HOOK, AFTER_CAMERA_HOOK, AFTER_EXPOSURE_HOOK


IMAGE_QUEUE_SIZE = 30


class PythonBackendAcquisition(Acquisition, metaclass=NumpyDocstringInheritanceMeta):
    """
    Pycro-Manager acquisition that uses a Python runtime backend.
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

        self._engine = Engine.get_instance()

        self._dataset = NDRAMDataset() if not directory else NDTiffDataset(directory, name=name, writable=True)
        self._finished = False
        self._notifications_finished = False
        self._create_event_queue()

        self._process_fn = image_process_fn
        self._image_processor = ImageProcessor(self) if image_process_fn is not None else None


        # create a thread that submits event_implementations
        # event_implementations can be added to the queue through image processors, hooks, or the acquire method
        def submit_events():
            while True:
                event_or_events = self._event_queue.get()
                if event_or_events is None:
                    self._finish()
                    self._events_finished.wait()
                    break
                _validate_acq_events(event_or_events)
                if isinstance(event_or_events, dict):
                    event_or_events = [event_or_events]
                # convert to objects
                event_or_events = [AcquisitionEvent.from_json(event, self) for event in event_or_events]
                Engine.get_instance().submit_event_iterator(iter(event_or_events))

        self._event_thread = threading.Thread(target=submit_events)
        self._event_thread.start()

        self._events_finished = threading.Event()
        self.abort_requested_ = threading.Event()
        self.start_time_ms_ = -1
        self.paused_ = False

        self.event_generation_hooks_ = []
        self.before_hardware_hooks_ = []
        self.before_z_hooks_ = []
        self.after_hardware_hooks_ = []
        self.after_camera_hooks_ = []
        self.after_exposure_hooks_ = []
        self.image_processors_ = []

        self.first_dequeue_ = queue.Queue(maxsize=IMAGE_QUEUE_SIZE)
        self.processor_output_queues_ = {}
        self.debug_mode_ = False
        self.abort_exception_ = None
        self.image_metadata_processor_ = None
        self.notification_handler_ = NotificationHandler()
        self.started_ = False
        self.core_ = Engine.get_core()
        self.data_sink_ = self._dataset

        summary_metadata = AcqEngMetadata.make_summary_metadata(self.core_, self)

        if self.data_sink_:
            self.data_sink_.initialize(summary_metadata)

        # receive notifications from the acquisition engine. Unlike the java_backend analog
        # of this, the python backend does not have a separate thread for notifications because
        # it can just use the one in AcqEngPy
        def post_notification(notification):
            self._notification_queue.put(notification)
            # these are processed seperately to handle image saved callback
            if AcqNotification.is_image_saved_notification(notification) or \
                    AcqNotification.is_data_sink_finished_notification(notification):
                self._image_notification_queue.put(notification)
                if self._image_notification_queue.qsize() > self._image_notification_queue.maxsize * 0.9:
                    warnings.warn(f"Acquisition image notification queue size: {self._image_notification_queue.qsize()}")

        self._add_acq_notification_listener(NotificationListener(post_notification))

        self._notification_dispatch_thread = self._start_notification_dispatcher(notification_callback_fn)

        # add hooks and image processor
        if pre_hardware_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(pre_hardware_hook_fn), self._acq.BEFORE_HARDWARE_HOOK)
        if post_hardware_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(post_hardware_hook_fn), self._acq.AFTER_HARDWARE_HOOK)
        if post_camera_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(post_camera_hook_fn), self._acq.AFTER_CAMERA_HOOK)
        if event_generation_hook_fn is not None:
            self._acq.add_hook(AcquisitionHook(event_generation_hook_fn), self._acq.EVENT_GENERATION_HOOK)
        if self._image_processor is not None:
            self._acq.add_image_processor(self._image_processor)

        # Monitor image arrival so they can be loaded on python side, but with no callback function
        # Need to do this regardless of whether you use it, so that notifcation handling shuts down
        self._storage_monitor_thread = self._add_storage_monitor_fn(image_saved_fn=image_saved_fn)


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

        self._start_saving_thread()
        self._post_notification(AcqNotification.create_acq_started_notification())
        self.started_ = True


    ########  Public API ###########

    def await_completion(self):
        """Wait for acquisition to finish and resources to be cleaned up"""
        try:
            while not self._are_events_finished() or (
                    self._dataset is not None and not self._dataset.is_finished()):
                self._check_for_exceptions()
                self._events_finished.wait(0.05)
                if self._dataset is not None:
                    self._dataset.block_until_finished(0.05)
                    # time.sleep(0.05) # does this prevent things from getting stuck?
                self._check_for_exceptions()
        finally:
            self._event_thread.join()
            self._notification_dispatch_thread.join()
            self._storage_monitor_thread.join()

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
        Called by the storage_implementations to check if all notifications have been processed
        """
        return self._notifications_finished


    def _post_notification(self, notification):
        self.notification_handler_.post_notification(notification)

    def _add_acq_notification_listener(self, post_notification_fn):
        self.notification_handler_.add_listener(post_notification_fn)

    def _save_image(self, image):
        if image is None:
            self.data_sink_.finish()
            self._post_notification(AcqNotification.create_data_sink_finished_notification())
        else:
            pixels, metadata = image.pix, image.tags
            axes = AcqEngMetadata.get_axes(metadata)
            self.data_sink_.put_image(axes, pixels, metadata)
            self._post_notification(AcqNotification.create_image_saved_notification(axes))

    def _start_saving_thread(self):
        def saving_thread(acq):
            try:
                while True:
                    if acq.debug_mode_:
                        acq.core_.log_message(f"Image queue size: {len(acq.first_dequeue_)}")
                    if not acq.image_processors_:
                        if acq.debug_mode_:
                            acq.core_.log_message("waiting for image to save")
                        img = acq.first_dequeue_.get()
                        if acq.debug_mode_:
                            acq.core_.log_message("got image to save")
                        acq._save_image(img)
                        if img is None:
                            break
                    else:
                        img = acq.processor_output_queues_[acq.image_processors_[-1]].get()
                        if acq.data_sink_:
                            if acq.debug_mode_:
                                acq.core_.log_message("Saving image")
                            if img.tags is None and img.pix is None:
                                break
                            acq._save_image(img)
                            if acq.debug_mode_:
                                acq.core_.log_message("Finished saving image")
            except Exception as ex:
                traceback.print_exc()
                acq.abort(ex)
            finally:
                acq._save_image(None)

        threading.Thread(target=saving_thread, args=(self,)).start()


    def _add_to_output(self, ti):
        try:
            if ti is None:
                self._events_finished.set()
            self.first_dequeue_.put(ti)
        except Exception as ex:
            raise RuntimeError(ex)

    def _finish(self):
        Engine.get_instance().finish_acquisition(self)

    def _abort(self, ex):
        if ex:
            self.abort_exception_ = ex
        if self.abort_requested_.is_set():
            return
        self.abort_requested_.set()
        if self.is_paused():
            self.set_paused(False)
        Engine.get_instance().finish_acquisition(self)

    def _check_for_exceptions(self):
        if self.abort_exception_:
            raise self.abort_exception_

    def _add_image_processor(self, p):
        if self.started_:
            raise RuntimeError("Cannot add processor after acquisition started")
        self.image_processors_.append(p)
        self.processor_output_queues_[p] = queue.Queue(maxsize=self.IMAGE_QUEUE_SIZE)
        if len(self.image_processors_) == 1:
            p.set_acq_and_queues(self, self.first_dequeue_, self.processor_output_queues_[p])
        else:
            p.set_acq_and_queues(self, self.processor_output_queues_[self.image_processors_[-2]],
                                 self.processor_output_queues_[self.image_processors_[-1]])

    def _add_hook(self, h, type_):
        if self.started_:
            raise RuntimeError("Cannot add hook after acquisition started")
        if type_ == EVENT_GENERATION_HOOK:
            self.event_generation_hooks_.append(h)
        elif type_ == BEFORE_HARDWARE_HOOK:
            self.before_hardware_hooks_.append(h)
        elif type_ == BEFORE_Z_DRIVE_HOOK:
            self.before_z_hooks_.append(h)
        elif type_ == AFTER_HARDWARE_HOOK:
            self.after_hardware_hooks_.append(h)
        elif type_ == AFTER_CAMERA_HOOK:
            self.after_camera_hooks_.append(h)
        elif type_ == AFTER_EXPOSURE_HOOK:
            self.after_exposure_hooks_.append(h)

    def _get_hooks(self, type):
        if type == EVENT_GENERATION_HOOK:
            return self.event_generation_hooks_
        elif type == BEFORE_HARDWARE_HOOK:
            return self.before_hardware_hooks_
        elif type == BEFORE_Z_DRIVE_HOOK:
            return self.before_z_hooks_
        elif type == AFTER_HARDWARE_HOOK:
            return self.after_hardware_hooks_
        elif type == AFTER_CAMERA_HOOK:
            return self.after_camera_hooks_
        elif type == AFTER_EXPOSURE_HOOK:
            return self.after_exposure_hooks_

    def _are_events_finished(self):
        return self._events_finished.is_set()

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
            if tagged_image is None:
                # this is a signal to stop
                self.output_queue.put(tagged_image)
                break
            process_fn_result = self._pycromanager_acq._call_image_process_fn(tagged_image.pix, tagged_image.tags)
            try:
                self._pycromanager_acq._check_for_exceptions()
            except Exception as e:
                # unclear if this is functioning properly, check later
                self._acq.abort()
            if process_fn_result is not None:
                # turn it into the expected tagged_image
                # TODO: change this on later unification of acq engines
                tagged_image.pix, tagged_image.tags = process_fn_result
                self.output_queue.put(tagged_image)
            # otherwise the image processor intercepted the image and nothing to do here

class AcquisitionHook:
    """
    Lightweight wrapper to convert function pointers to AcqEng hooks
    """

    def __init__(self, hook_fn):
        self._hook_fn = hook_fn

    def run(self, event):
        if AcquisitionEvent.is_acquisition_finished_event(event):
            return event
        acq = event.acquisition_
        try:
            output = self._hook_fn(event.to_json())
        except Exception as e:
            acq.abort()
            traceback.print_exc()
            return # cancel event and let the shutdown process handle the exception
        if output is not None:
            return AcquisitionEvent.from_json(output, acq)

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