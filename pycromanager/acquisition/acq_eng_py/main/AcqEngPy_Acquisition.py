import json
import queue
import traceback
import threading

from pycromanager.acquisition.acq_eng_py.main.acq_eng_metadata import AcqEngMetadata
from pycromanager.acquisition.acq_eng_py.internal.engine import Engine
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification
from pycromanager.acquisition.acq_eng_py.internal.notification_handler import NotificationHandler



class Acquisition():

    EVENT_GENERATION_HOOK = 0
    # This hook runs before changes to the hardware (corresponding to the instructions in the
    # event) are made
    BEFORE_HARDWARE_HOOK = 1
    # This hook runs after changes to the hardware took place, but before camera exposure
    # (either a snap or a sequence) is started
    AFTER_HARDWARE_HOOK = 2
    # Hook runs after the camera sequence acquisition has started. This can be used for
    # external triggering of the camera
    AFTER_CAMERA_HOOK = 3
    # Hook runs after the camera exposure ended (when possible, before readout of the camera
    # and availability of the images in memory).
    AFTER_EXPOSURE_HOOK = 4

    IMAGE_QUEUE_SIZE = 30

    def __init__(self, sink, summary_metadata_processor=None, initialize=True):
        self.xy_stage_ = None
        self.events_finished_ = threading.Event()
        self.abort_requested_ = threading.Event()
        self.start_time_ms_ = -1
        self.paused_ = False
        self.event_generation_hooks_ = []
        self.before_hardware_hooks_ = []
        self.after_hardware_hooks_ = []
        self.after_camera_hooks_ = []
        self.after_exposure_hooks_ = []
        self.image_processors_ = []
        self.first_dequeue_ = queue.Queue(maxsize=self.IMAGE_QUEUE_SIZE)
        self.processor_output_queues_ = {}
        self.debug_mode_ = False
        self.abort_exception_ = None
        self.image_metadata_processor_ = None
        self.notification_handler_ = NotificationHandler()
        self.started_ = False
        self.core_ = Engine.get_core()
        self.summary_metadata_processor_ = summary_metadata_processor
        self.data_sink_ = sink
        if initialize:
            self.initialize()

    def post_notification(self, notification):
        self.notification_handler_.post_notification(notification)

    def add_acq_notification_listener(self, post_notification_fn):
        self.notification_handler_.add_listener(post_notification_fn)

    def get_data_sink(self):
        return self.data_sink_

    def set_debug_mode(self, debug):
        self.debug_mode_ = debug

    def is_debug_mode(self):
        return self.debug_mode_

    def is_abort_requested(self):
        return self.abort_requested_.is_set()

    def abort(self, e=None):
        if e:
            self.abort_exception_ = e
        if self.abort_requested_.is_set():
            return
        self.abort_requested_.set()
        if self.is_paused():
            self.set_paused(False)
        Engine.get_instance().finish_acquisition(self)

    def check_for_exceptions(self):
        if self.abort_exception_:
            raise self.abort_exception_

    def add_to_summary_metadata(self, summary_metadata):
        if self.summary_metadata_processor_:
            self.summary_metadata_processor_(summary_metadata)

    def add_to_image_metadata(self, tags):
        if self.image_metadata_processor_:
            self.image_metadata_processor_(tags)

    def add_tags_to_tagged_image(self, tags, more_tags):
        if not more_tags:
            return
        more_tags_object = json.loads(json.dumps(more_tags))
        tags['AcqEngMetadata.TAGS'] = more_tags_object

    def submit_event_iterator(self, evt):
        if not self.started_:
            self.start()
        return Engine.get_instance().submit_event_iterator(evt)

    def start_saving_thread(self):
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
                        if img.tags is None and img.pix is None:
                            break
                        acq.save_image(img)
                    else:
                        img = acq.processor_output_queues_[acq.image_processors_[-1]].get()
                        if acq.data_sink_:
                            if acq.debug_mode_:
                                acq.core_.log_message("Saving image")
                            if not img.pix and not img.tags:
                                break
                            acq.save_image(img)
                            if acq.debug_mode_:
                                acq.core_.log_message("Finished saving image")
            except Exception as ex:
                traceback.print_exc()
                acq.abort(ex)
            finally:
                acq.save_image(acq.core_.TaggedImage(None, None))

        threading.Thread(target=saving_thread, args=(self,)).start()

    def add_image_processor(self, p):
        if self.started_:
            raise RuntimeError("Cannot add processor after acquisition started")
        self.image_processors_.append(p)
        self.processor_output_queues_[p] = queue.Queue(maxsize=self.IMAGE_QUEUE_SIZE)
        if len(self.image_processors_) == 1:
            p.set_acq_and_queues(self, self.first_dequeue_, self.processor_output_queues_[p])
        else:
            p.set_acq_and_queues(self, self.processor_output_queues_[self.image_processors_[-2]],
                                   self.processor_output_queues_[self.image_processors_[-1]])

    def add_hook(self, h, type_):
        if self.started_:
            raise RuntimeError("Cannot add hook after acquisition started")
        if type_ == self.EVENT_GENERATION_HOOK:
            self.event_generation_hooks_.append(h)
        elif type_ == self.BEFORE_HARDWARE_HOOK:
            self.before_hardware_hooks_.append(h)
        elif type_ == self.AFTER_HARDWARE_HOOK:
            self.after_hardware_hooks_.append(h)
        elif type_ == self.AFTER_CAMERA_HOOK:
            self.after_camera_hooks_.append(h)
        elif type_ == self.AFTER_EXPOSURE_HOOK:
            self.after_exposure_hooks_.append(h)

    def initialize(self):
        if self.core_:
            summary_metadata = AcqEngMetadata.make_summary_metadata(self.core_, self)
            self.add_to_summary_metadata(summary_metadata)
            try:
                self.summary_metadata_ = summary_metadata
            except json.JSONDecodeError:
                print("Couldn't copy summary metadata")
            if self.data_sink_:
                self.data_sink_.initialize(self, summary_metadata)

    def start(self):
        if self.data_sink_:
            self.start_saving_thread()
        self.post_notification(AcqNotification.create_acq_started_notification())
        self.started_ = True

    def save_image(self, image):
        if image.tags is None and image.pix is None:
            self.data_sink_.finish()
            self.post_notification(AcqNotification.create_data_sink_finished_notification())
        else:
            self.data_sink_.put_image(image)
            axes = AcqEngMetadata.get_axes(image.tags)
            self.post_notification(AcqNotification.create_image_saved_notification(axes))

    def get_start_time_ms(self):
        return self.start_time_ms_

    def set_start_time_ms(self, time):
        self.start_time_ms_ = time

    def is_paused(self):
        return self.paused_

    def is_started(self):
        return self.started_

    def set_paused(self, pause):
        self.paused_ = pause

    def get_summary_metadata(self):
        return self.summary_metadata_

    def anything_acquired(self):
        return not self.data_sink_ or self.data_sink_.anything_acquired()

    def add_image_metadata_processor(self, processor):
        if not self.image_metadata_processor_:
            self.image_metadata_processor_ = processor
        else:
            raise RuntimeError("Multiple metadata processors not supported")

    def get_event_generation_hooks(self):
        return self.event_generation_hooks_

    def get_before_hardware_hooks(self):
        return self.before_hardware_hooks_

    def get_after_hardware_hooks(self):
        return self.after_hardware_hooks_

    def get_after_camera_hooks(self):
        return self.after_camera_hooks_

    def get_after_exposure_hooks(self):
        return self.after_exposure_hooks_

    def add_to_output(self, ti):
        try:
            if ti.tags is None and ti.pix is None:
                self.events_finished_.set()
            self.first_dequeue_.put(ti)
        except Exception as ex:
            raise RuntimeError(ex)

    def finish(self):
        Engine.get_instance().finish_acquisition(self)

    def are_events_finished(self):
        return self.events_finished_.is_set()

    def block_until_events_finished(self, timeout=None):
        """Blocks until all events have been processed."""
        self.events_finished_.wait(timeout)

    def block_unless_aborted(self, timeout_ms=None):
        """Blocks until acquisition is aborted."""
        self.abort_requested_.wait(timeout_ms / 1000)


    def get_image_transfer_queue_size(self):
        return self.IMAGE_QUEUE_SIZE

    def get_image_transfer_queue_count(self):
        return len(self.first_dequeue_)


