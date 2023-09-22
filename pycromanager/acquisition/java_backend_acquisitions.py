"""
The Pycro-manager Acquisiton system
"""
import warnings
import weakref

import numpy as np
import multiprocessing
import threading
from inspect import signature
import time
from pycromanager.zmq_bridge.bridge import deserialize_array
from pycromanager.zmq_bridge.wrappers import PullSocket, PushSocket, JavaObject, JavaClass
from pycromanager.zmq_bridge.wrappers import DEFAULT_BRIDGE_PORT as DEFAULT_PORT
from pycromanager.mm_java_classes import ZMQRemoteMMCoreJ, Magellan
from ndtiff import Dataset
import os.path
import queue
from docstring_inheritance import NumpyDocstringInheritanceMeta
from pycromanager.acquisition.acquisition_superclass import Acquisition
import traceback
from pycromanager.acq_future import AcqNotification, AcquisitionFuture



### These functions are defined outside the Acquisition class to
# prevent problems with pickling when running them in differnet process
# although they are currently only used in different threads

def _run_acq_event_source(acquisition, event_port, event_queue, debug=False):
    event_socket = PushSocket(event_port, debug=debug)
    try:
        while True:
            events = event_queue.get(block=True)
            if debug:
                print("got event(s):", events)
            if events is None:
                # Initiate the normal shutdown process
                if not acquisition._acq.is_finished():
                    # if it has been finished through something happening on the other side
                    event_socket.send({"events": [{"special": "acquisition-end"}]})
                    # wait for signal that acquisition has received the end signal
                    while not acquisition._acq.is_finished():
                        acquisition._acq.block_until_events_finished(0.01)
                break
            # it may have been shut down remotely (e.g. by user Xing out viewer)
            # if we try to send an event at this time, it will hang indefinitely
            if acquisition._acq.is_finished():
                break
            # TODO in theory it could be aborted in between the check above and sending below,
            #  maybe consider putting a timeout on the send?
            event_socket.send({"events": events if type(events) == list else [events]})
            if debug:
                print("sent events")
    except Exception as e:
        acquisition.abort(e)
    finally:
        event_socket.close()


def _run_acq_hook(acquisition, pull_port,
                  push_port, hook_connected_evt, event_queue, hook_fn, debug=False):

    push_socket = PushSocket(pull_port, debug=debug)
    pull_socket = PullSocket(push_port, debug=debug)
    hook_connected_evt.set()

    exception = None
    while True:
        event_msg = pull_socket.receive()

        if "special" in event_msg and event_msg["special"] == "acquisition-end":
            push_socket.send(event_msg)
            push_socket.close()
            pull_socket.close()
            return
        else:
            if "events" in event_msg.keys():
                event_msg = event_msg["events"]  # convert from sequence
            params = signature(hook_fn).parameters
            if len(params) == 1 or len(params) == 2:
                try:
                    if len(params) == 1:
                        new_event_msg = hook_fn(event_msg)
                    elif len(params) == 2:
                        new_event_msg = hook_fn(event_msg, event_queue)
                except Exception as e:
                    acquisition.abort(e)
                    # Cancel the execution of event because there was an exception
                    new_event_msg = None
                    # don't return here--wait for the signal from the acq engine
            else:
                acquisition.abort(Exception("Incorrect number of arguments for hook function. Must be 1 or 2"))

        if isinstance(new_event_msg, list):
            new_event_msg = {
                "events": new_event_msg
            }  # convert back to the expected format for a sequence
        push_socket.send(new_event_msg)


def _run_image_processor(
        acquisition, pull_port, push_port, sockets_connected_evt, process_fn, event_queue, debug
):
    acquisition._process_fn = process_fn
    push_socket = PushSocket(pull_port, debug=debug)
    pull_socket = PullSocket(push_port, debug=debug)
    if debug:
        print("image processing sockets connected")
    sockets_connected_evt.set()

    def process_and_sendoff(image_tags_tuple, original_dtype):
        """

        Parameters
        ----------
        image_tags_tuple :


        Returns
        -------

        """
        if len(image_tags_tuple) != 2:
            acquisition.abort(Exception("If image is returned, it must be of the form (pixel, metadata)"))

        pixels = image_tags_tuple[0]
        metadata = image_tags_tuple[1]

        # only accepts same pixel type as original
        if not np.issubdtype(image_tags_tuple[0].dtype, original_dtype) and not np.issubdtype(
            original_dtype, image_tags_tuple[0].dtype
        ):
            acquisition.abort(Exception(
                "Processed image pixels must have same dtype as input image pixels, "
                "but instead they were {} and {}".format(image_tags_tuple[0].dtype, pixels.dtype)
            ))

        if metadata['PixelType'] == 'RGB32':
            if pixels.shape[-1] == 3:
                #append 0 for alpha channel because thats whats expected
                pixels = np.concatenate([pixels, np.zeros_like(pixels[..., 0])[..., None]], axis=2)
        else:
            #maybe pixel type was changed by processing?
            metadata["PixelType"] = "GRAY8" if pixels.dtype.itemsize == 1 else "GRAY16"

        processed_img = {
            "pixels": pixels.tobytes(),
            "metadata": metadata,
        }
        push_socket.send(processed_img, suppress_debug_message=True)

    while True:
        message = None
        while message is None:
            message = pull_socket.receive(timeout=30, suppress_debug_message=True)  # check for new message

        if "special" in message and message["special"] == "finished":
            pull_socket.close()
            push_socket.send(message)  # Continue propagating the finished signal
            push_socket.close()
            return

        metadata = message["metadata"]
        # TODO: this should probably be handled by the push socket...
        pixels = deserialize_array(message["pixels"])
        if metadata['PixelType'] == 'RGB32':
            image = np.reshape(pixels, [metadata["Height"], metadata["Width"], 4])[..., :3]
        else:
            image = np.reshape(pixels, [metadata["Height"], metadata["Width"]])

        processed = acquisition._call_image_process_fn(image, metadata)

        if processed is None:
            continue

        if type(processed) == list:
            for image in processed:
                process_and_sendoff(image, pixels.dtype)
        else:
            process_and_sendoff(processed, pixels.dtype)

def _notification_handler_fn(acquisition, notification_push_port, connected_event, debug=False):
    monitor_socket = PullSocket(notification_push_port)
    connected_event.set()

    try:
        events_finished = False
        data_sink_finished = False
        while True:
            message = monitor_socket.receive()
            notification = AcqNotification.from_json(message)
            # these are processed seperately to handle image saved callback
            if AcqNotification.is_image_saved_notification(notification):
                if not notification.is_data_sink_finished_notification():
                    # decode the NDTiff index entry
                    index_entry = notification.id.encode('ISO-8859-1')
                    axes = acquisition._dataset._add_index_entry(index_entry)
                    # swap the notification id from the byte array of index information to axes
                    notification.id = axes
                acquisition._image_notification_queue.put(notification)
            acquisition._notification_queue.put(notification)
            if AcqNotification.is_acquisition_finished_notification(notification):
                events_finished = True
            elif AcqNotification.is_data_sink_finished_notification(notification):
                data_sink_finished = True
                acquisition._image_notification_queue.put(notification)
            if events_finished and data_sink_finished:
                break

    except Exception as e:
        traceback.print_exc()
        acquisition.abort(e)
    finally:
        monitor_socket.close()


class JavaBackendAcquisition(Acquisition, metaclass=NumpyDocstringInheritanceMeta):
    """
    Pycro-Manager acquisition that uses a Java runtime backend via a ZeroMQ communication layer.
    """

    def __init__(
        self,
        directory: str=None,
        name: str='default_acq_name',
        image_process_fn : callable=None,
        event_generation_hook_fn: callable=None,
        pre_hardware_hook_fn: callable=None,
        post_hardware_hook_fn: callable=None,
        post_camera_hook_fn: callable=None,
        notification_callback_fn: callable=None,
        image_saved_fn: callable=None,
        show_display: bool=True,
        napari_viewer=None,
        saving_queue_size: int=20,
        timeout: int=2000,
        port: int=DEFAULT_PORT,
        debug: int=False
    ):
        """
        Parameters
        ----------
        show_display : bool
            If True, show the image viewer window. If False, show no viewer.
        saving_queue_size : int
            The number of images to queue (in memory) while waiting to write to disk. Higher values should
            in theory allow sequence acquisitions to go faster, but requires the RAM to hold images while
            they are waiting to save
        timeout :
            Timeout in ms for connecting to Java side
        port :
            Allows overriding the default port for using Java backends on a different port. Use this
            after calling start_headless with the same non-default port
        """
        # Get a dict of all named argument values (or default values when nothing provided)
        arg_names = [k for k in signature(JavaBackendAcquisition.__init__).parameters.keys() if k != 'self']
        l = locals()
        named_args = {arg_name: (l[arg_name] if arg_name in l else
                                     dict(signature(JavaBackendAcquisition.__init__).parameters.items())[arg_name].default)
                                     for arg_name in arg_names }


        superclass_arg_names = [k for k in signature(Acquisition.__init__).parameters.keys() if k != 'self']
        superclass_args = {key: named_args[key] for key in superclass_arg_names}
        super().__init__(**superclass_args)

        if directory is not None:
            # Expend ~ in path
            directory = os.path.expanduser(directory)
            # If path is relative, retain knowledge of the current working directory
            self._directory = os.path.abspath(directory)
        else:
            self._directory = None
        named_args['directory'] = self._directory

        # Java specific parameters
        self._port = port
        self._timeout = timeout
        self._nd_viewer = None

        self._create_event_queue()
        self._create_remote_acquisition(**named_args)
        self._initialize_image_processor(**named_args)
        self._initialize_hooks(**named_args)

        try:
            self._remote_notification_handler = JavaObject('org.micromanager.remote.RemoteNotificationHandler',
                                                           args=[self._acq], port=self._port, new_socket=False)
            self._acq_notification_recieving_thread = self._start_receiving_notifications()
            self._acq_notification_dispatcher_thread = self._start_notification_dispatcher(notification_callback_fn)
        # TODO: can remove this after this feature has been present for a while
        except:
            traceback.print_exc()
            warnings.warn('Could not create acquisition notification handler. '
                          'Update Micro-Manager and Pyrcro-Manager to the latest versions to fix this')

        # Start remote acquisition
        # Acquistition.start is now deprecated, so this can be removed later
        # Acquisitions now get started automatically when the first events submitted
        # but Magellan acquisitons (and probably others that generate their own events)
        # will need some new method to submit events only after image processors etc have been added
        self._acq.start()
        self._dataset_disk_location = (
            self._acq.get_data_sink().get_storage().get_disk_location()
            if self._acq.get_data_sink() is not None
            else None
        )

        self._start_events()

        # Load remote storage
        data_sink = self._acq.get_data_sink()
        if data_sink is not None:
            # load a view of the dataset in progress. This is used so that acq.get_dataset() can be called
            # while the acquisition is still running, and (optionally )so that a image_saved_fn can be called
            # when images are written to disk
            ndtiff_storage = data_sink.get_storage()
            summary_metadata = ndtiff_storage.get_summary_metadata()
            if directory is not None:
                self._dataset = Dataset(dataset_path=self._dataset_disk_location, _summary_metadata=summary_metadata)
                # Monitor image arrival so they can be loaded on python side, but with no callback function
                # Need to do this regardless of whether you use it, so that it signals to shut down on Java side
                self._storage_monitor_thread = self._add_storage_monitor_fn(image_saved_fn=image_saved_fn)

        if show_display:
            if napari_viewer is None:
                # using NDViewer
                self._nd_viewer = self._acq.get_data_sink().get_viewer()
            else:
                # using napari viewer
                try:
                    import napari
                except:
                    raise Exception('Napari must be installed in order to use this feature')
                from pycromanager.napari_util import start_napari_signalling
                assert isinstance(napari_viewer, napari.Viewer), 'napari_viewer must be an instance of napari.Viewer'
                self._napari_viewer = napari_viewer
                start_napari_signalling(self._napari_viewer, self.get_dataset())


    ########  Public API methods with unique implementations for Java backend ###########
    def get_dataset(self):
        if self._finished:
            if self._dataset is None:
                self._dataset = Dataset(self._dataset_disk_location)

        return self._dataset

    def await_completion(self):
        while not self._acq.are_events_finished() or (
                self._acq.get_data_sink() is not None and not self._acq.get_data_sink().is_finished()):
            self._check_for_exceptions()
            self._acq.block_until_events_finished(0.01)
        # This will block until saving is finished, if there is a data sink
        self._acq.wait_for_completion()
        self._check_for_exceptions()

        for hook_thread in self._hook_threads:
            hook_thread.join()

        if hasattr(self, '_event_thread'):
            self._event_thread.join()

        # need to do this so its _Bridge can be garbage collected and a reference to the JavaBackendAcquisition
        # does not prevent Bridge cleanup and process exiting
        self._remote_acq = None

        # Wait on all the other threads to shut down properly
        if hasattr(self, '_storage_monitor_thread'):
            self._storage_monitor_thread.join()

        if hasattr(self, '_acq_notification_recieving_thread'):
            # for backwards compatiblitiy with older versions of Pycromanager java before this added
            self._acq_notification_recieving_thread.join()
            self._remote_notification_handler.notification_handling_complete()
            # need to do this so its _Bridge can be garbage collected and a reference to the JavaBackendAcquisition
            # does not prevent Bridge cleanup and process exiting
            self._remote_notification_handler = None
            self._acq_notification_dispatcher_thread.join()

        self._acq = None
        self._finished = True


    def get_viewer(self):
        if self._napari_viewer is None:
            return self._nd_viewer
        else:
            return self._napari_viewer

    ########  Private methods ###########
    def _start_receiving_notifications(self):
        """
        Thread that runs a function that pulls notifications from the acquisition engine and puts them on a queue
        """
        connected_event = threading.Event()

        pull_port = self._remote_notification_handler.get_port()
        notification_thread = threading.Thread(
            target=_notification_handler_fn,
            args=(
                self,
                pull_port,
                connected_event,
                self._debug,
            ),
            name="NotificationHandlerThread",
        )
        #
        # Wait for pulling to start before you signal for pushing to start
        notification_thread.start()
        connected_event.wait()

        # start pushing out all the notifications
        self._remote_notification_handler.start()
        return notification_thread

    def _add_storage_monitor_fn(self, image_saved_fn=None):
        """
        Add a callback function that gets called whenever a new image is writtern to disk (for acquisitions in
        progress only)

        Parameters
        ----------
        image_saved_fn : Callable
            user function to be run whenever an image is ready on disk
        """
        # TODO: this should read from a queue of image-specific notifications and dispatch accordingly

        callback = None
        if image_saved_fn is not None:
            params = signature(image_saved_fn).parameters
            if len(params) == 2:
                callback = image_saved_fn
            elif len(params) == 3:
                callback = lambda axes, dataset: image_saved_fn(axes, dataset, self._event_queue)
            else:
                raise Exception('Image saved callbacks must have either 2 or three parameters')

        def _storage_monitor_fn():
            dataset = self.get_dataset()
            while True:
                image_notification = self._image_notification_queue.get()
                if AcqNotification.is_data_sink_finished_notification(image_notification):
                    break
                dataset._new_image_arrived = True
                if callback is not None:
                    callback(image_notification.id, dataset)
        t = threading.Thread(target=_storage_monitor_fn, name='StorageMonitorThread')
        t.start()
        return t

    def _check_for_exceptions(self):
        """
        Check for exceptions on the python side (i.e. hooks and processors)
        or on the Java side (i.e. hardware control)
        """
        # these will throw exceptions
        self._acq.check_for_exceptions()
        if self._exception is not None:
            raise self._exception

    def _start_events(self, **kwargs):

        self.event_port = self._acq.get_event_port()

        self._event_thread = threading.Thread(
            target=_run_acq_event_source,
            args=(self, self.event_port, self._event_queue, self._debug),
            name="Event sending",
        )
        self._event_thread.start()

    def _initialize_image_processor(self, **kwargs):

        if kwargs['image_process_fn'] is not None:
            java_processor = JavaObject(
                "org.micromanager.remote.RemoteImageProcessor", port=self._port
            )
            self._acq.add_image_processor(java_processor)
            self._processor_thread = self._start_processor(
                java_processor, kwargs['image_process_fn'],
                # Some acquisitions (e.g. Explore acquisitions) create events on Java side
                self._event_queue if hasattr(self, '_event_queue') else None,
                process=False)

    def _initialize_hooks(self, **kwargs):
        self._hook_threads = []
        if kwargs['event_generation_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['event_generation_hook_fn'],
                                                       self._event_queue, process=False))
            self._acq.add_hook(hook, self._acq.EVENT_GENERATION_HOOK)
        if kwargs['pre_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._acq]
            )
            self._hook_threads.append(self._start_hook(hook,
                                            kwargs['pre_hardware_hook_fn'], self._event_queue,
                                                       process=False))
            self._acq.add_hook(hook, self._acq.BEFORE_HARDWARE_HOOK)
        if kwargs['post_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_hardware_hook_fn'],
                                                       self._event_queue, process=False))
            self._acq.add_hook(hook, self._acq.AFTER_HARDWARE_HOOK)
        if kwargs['post_camera_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._acq],
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_camera_hook_fn'],
                                                       self._event_queue, process=False))
            self._acq.add_hook(hook, self._acq.AFTER_CAMERA_HOOK)

    def _create_remote_acquisition(self, **kwargs):
        core = ZMQRemoteMMCoreJ(port=self._port, timeout=self._timeout, debug=self._debug)
        acq_factory = JavaObject("org.micromanager.remote.RemoteAcquisitionFactory",
            # create a new socket for it to run on so that it can have blocking calls without interfering with
            # the main socket or other internal sockets
            new_socket=True,
            port=self._port, args=[core], debug=self._debug)
        show_viewer = kwargs['show_display'] is True and kwargs['napari_viewer'] is None
        self._acq = acq_factory.create_acquisition(kwargs['directory'], kwargs['name'], show_viewer,
                                                   kwargs['saving_queue_size'], self._debug,)

    def _start_hook(self, remote_hook, remote_hook_fn : callable, event_queue, process):
        """

        Parameters
        ----------
        remote_hook :

        remote_hook_fn :

        event_queue :

        process :


        Returns
        -------

        """
        hook_connected_evt = multiprocessing.Event() if process else threading.Event()

        pull_port = remote_hook.get_pull_port()
        push_port = remote_hook.get_push_port()

        hook_thread = (multiprocessing.Process if process else threading.Thread)(
            target=_run_acq_hook,
            name="AcquisitionHook",
            args=(
                self,
                pull_port,
                push_port,
                hook_connected_evt,
                event_queue,
                remote_hook_fn,
                self._debug,
            ),
        )
        # if process else threading.Thread(target=_acq_hook_fn, args=(), name='AcquisitionHook')
        hook_thread.start()

        hook_connected_evt.wait()  # wait for push/pull sockets to connect
        return hook_thread

    def _start_processor(self, processor, process_fn, event_queue, process):
        """

        Parameters
        ----------
        processor :

        process_fn :

        event_queue :

        process :


        Returns
        -------

        """
        # this must start first
        processor.start_pull()

        sockets_connected_evt = multiprocessing.Event() if process else threading.Event()

        pull_port = processor.get_pull_port()
        push_port = processor.get_push_port()

        processor_thread = (multiprocessing.Process if process else threading.Thread)(
            target=_run_image_processor,
            args=(
                self,
                pull_port,
                push_port,
                sockets_connected_evt,
                process_fn,
                event_queue,
                self._debug,
            ),
            name="ImageProcessor",
        )
        processor_thread.start()

        sockets_connected_evt.wait()  # wait for push/pull sockets to connect
        processor.start_push()
        return processor_thread


class XYTiledAcquisition(JavaBackendAcquisition):
    """
    For making tiled images with an XY stage and multiresolution saving
    (e.g. for making one large contiguous image of a sample larger than the field of view)
    """

    def __init__(
            self,
            tile_overlap : int or tuple,
            directory: str=None,
            name: str=None,
            max_multi_res_index: int=None,
            image_process_fn: callable=None,
            pre_hardware_hook_fn: callable=None,
            post_hardware_hook_fn: callable=None,
            post_camera_hook_fn: callable=None,
            show_display: bool=True,
            image_saved_fn: callable=None,
            saving_queue_size: int=20,
            timeout: int=1000,
            port: int=DEFAULT_PORT,
            debug: bool=False,
    ):
        """
        Parameters
        ----------
        tile_overlap : int or tuple of int
            If given, XY tiles will be laid out in a grid and multi-resolution saving will be
            actived. Argument can be a two element tuple describing the pixel overlaps between adjacent
            tiles. i.e. (pixel_overlap_x, pixel_overlap_y), or an integer to use the same overlap for both.
            For these features to work, the current hardware configuration must have a valid affine transform
            between camera coordinates and XY stage coordinates
        max_multi_res_index : int
            Maximum index to downsample to in multi-res pyramid mode. 0 is no downsampling,
            1 is downsampled up to 2x, 2 is downsampled up to 4x, etc. If not provided, it will be dynamically
            calculated and updated from data
        """
        self.tile_overlap = tile_overlap
        self.max_multi_res_index = max_multi_res_index
        # Collct all argument values except the ones specific to XY Tiled acquisitions
        arg_names = list(signature(self.__init__).parameters.keys())
        arg_names.remove('tile_overlap')
        arg_names.remove('max_multi_res_index')
        l = locals()
        named_args = {arg_name: l[arg_name] for arg_name in arg_names}
        super().__init__(**named_args)

    def _create_remote_acquisition(self, port, **kwargs):
        core = ZMQRemoteMMCoreJ(port=self._port, timeout=self._timeout)
        acq_factory = JavaObject(
            "org.micromanager.remote.RemoteAcquisitionFactory", port=self._port, args=[core]
        )

        show_viewer = kwargs['show_display'] is True and\
                      kwargs['napari_viewer'] is None and\
                      (kwargs['directory'] is not None and kwargs['name'] is not None)
        if type(self.tile_overlap) is tuple:
            x_overlap, y_overlap = self.tile_overlap
        else:
            x_overlap = self.tile_overlap
            y_overlap = self.tile_overlap

        self._remote_acq = acq_factory.create_tiled_acquisition(
            kwargs['directory'],
            kwargs['name'],
            show_viewer,
            True,
            x_overlap,
            y_overlap,
            self.max_multi_res_index if self.max_multi_res_index is not None else -1,
            kwargs['saving_queue_size'],
            self._debug,
        )

class ExploreAcquisition(JavaBackendAcquisition):
    """
    Launches a user interface for an "Explore Acquisition"--a type of XYTiledAcquisition
    in which acquisition events come from the user dynamically driving the stage and selecting
    areas to image
    """

    def __init__(
            self,
            directory: str,
            name: str,
            z_step_um: float,
            tile_overlap: int or tuple,
            channel_group: str = None,
            image_process_fn: callable=None,
            pre_hardware_hook_fn: callable=None,
            post_hardware_hook_fn: callable=None,
            post_camera_hook_fn: callable=None,
            show_display: bool=True,
            image_saved_fn: callable=None,
            saving_queue_size: int=20,
            timeout: int=1000,
            port: int=DEFAULT_PORT,
            debug: bool=False,
    ):
        """
        Parameters
        ----------
        z_step_um : str
            Spacing between successive z planes, in microns
        tile_overlap : int or tuple of int
            If given, XY tiles will be laid out in a grid and multi-resolution saving will be
            activated. Argument can be a two element tuple describing the pixel overlaps between adjacent
            tiles. i.e. (pixel_overlap_x, pixel_overlap_y), or an integer to use the same overlap for both.
            For these features to work, the current hardware configuration must have a valid affine transform
            between camera coordinates and XY stage coordinates
        channel_group : str
            Name of a config group that provides selectable channels
        """
        self.tile_overlap = tile_overlap
        self.channel_group = channel_group
        self.z_step_um = z_step_um
        # Collct all argument values except the ones specific to ExploreAcquisitions
        arg_names = list(signature(self.__init__).parameters.keys())
        arg_names.remove('tile_overlap')
        arg_names.remove('z_step_um')
        arg_names.remove('channel_group')
        l = locals()
        named_args = {arg_name: l[arg_name] for arg_name in arg_names}
        super().__init__(**named_args)

    def _create_remote_acquisition(self, port, **kwargs):
        if type(self.tile_overlap) is tuple:
            x_overlap, y_overlap = self.tile_overlap
        else:
            x_overlap = self.tile_overlap
            y_overlap = self.tile_overlap

        ui_class = JavaClass('org.micromanager.explore.ExploreAcqUIAndStorage')
        ui = ui_class.create(kwargs['directory'], kwargs['name'], x_overlap, y_overlap, self.z_step_um, self.channel_group)
        self._remote_acq = ui.get_acquisition()

    def _start_events(self, **kwargs):
        pass # These come from the user

    def _create_event_queue(self, **kwargs):
        pass # Comes from the user


class MagellanAcquisition(JavaBackendAcquisition):
    """
    Class used for launching Micro-Magellan acquisitions. Must pass either magellan_acq_index
    or magellan_explore as an argument
    """

    def __init__(
            self,
            magellan_acq_index: int=None,
            magellan_explore: bool=False,
            image_process_fn: callable=None,
            event_generation_hook_fn: callable=None,
            pre_hardware_hook_fn: callable=None,
            post_hardware_hook_fn: callable=None,
            post_camera_hook_fn: callable=None,
            image_saved_fn: callable=None,
            timeout: int=500,
            port: int=DEFAULT_PORT,
            debug: bool=False,
    ):
        """
        Parameters
        ----------
        magellan_acq_index : int
            run this acquisition using the settings specified at this position in the main
            GUI of micro-magellan (micro-manager plugin). This index starts at 0
        magellan_explore : bool
            Run a Micro-magellan explore acquisition
        """
        self.magellan_acq_index = magellan_acq_index
        self.magellan_explore = magellan_explore
        # Collct all argument values except the ones specific to Magellan
        arg_names = list(signature(self.__init__).parameters.keys())
        arg_names.remove('magellan_acq_index')
        arg_names.remove('magellan_explore')
        l = locals()
        named_args = {arg_name: l[arg_name] for arg_name in arg_names}
        super().__init__(**named_args)

    def _start_events(self, **kwargs):
        pass # Magellan handles this on Java side

    def _create_event_queue(self, **kwargs):
        pass # Magellan handles this on Java side

    def _create_remote_acquisition(self, **kwargs):
        magellan_api = Magellan()
        if self.magellan_acq_index is not None:
            self._remote_acq = magellan_api.create_acquisition(self.magellan_acq_index, False)
        elif self.magellan_explore:
            self._remote_acq = magellan_api.create_explore_acquisition(False)
        self._event_queue = None
