"""
The Pycro-manager Acquisiton system
"""
import warnings

import numpy as np
import multiprocessing
import threading
from inspect import signature
import time
from pycromanager.zmq_bridge._bridge import deserialize_array
from pycromanager.zmq_bridge.wrappers import PullSocket, PushSocket, JavaObject, JavaClass
from pycromanager.zmq_bridge.wrappers import DEFAULT_BRIDGE_PORT as DEFAULT_PORT
from pycromanager.mm_java_classes import Core, Magellan
from ndtiff import Dataset
import os.path
import queue
from docstring_inheritance import NumpyDocstringInheritanceMeta


### These functions are defined outside the Acquisition class to
# prevent problems with pickling when running them in differnet process

def _run_acq_event_source(acquisition, event_port, event_queue, debug=False):
    event_socket = PushSocket(event_port, debug=debug)
    while True:
        try:
            events = event_queue.get(block=True)
            if debug:
                print("got event(s):", events)
            if events is None:
                # Time to shut down
                event_socket.send({"events": [{"special": "acquisition-end"}]})
                # wait for signal that acquisition has received the end signal
                while not acquisition._remote_acq.are_events_finished():
                    time.sleep(0.001)
                event_socket.close()
                return
            event_socket.send({"events": events if type(events) == list else [events]})
            if debug:
                print("sent events")
        except Exception as e:
            acquisition.abort(e)
            # continue here, as abort will shut things down in an orderly fashion


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

        params = signature(process_fn).parameters
        processed = None
        if len(params) == 2 or len(params) == 3:
            try:
                if len(params) == 2:
                    processed = process_fn(image, metadata)
                elif len(params) == 3:
                    processed = process_fn(image, metadata, event_queue)
            except Exception as e:
                acquisition.abort(Exception("exception in image processor: {}".format(e)))
                continue
        else:
            acquisition.abort(Exception(
                "Incorrect number of arguments for image processing function, must be 2 or 3"
            ))

        if processed is None:
            continue

        if type(processed) == list:
            for image in processed:
                process_and_sendoff(image, pixels.dtype)
        else:
            process_and_sendoff(processed, pixels.dtype)

def _storage_monitor_fn(acquisition, dataset, storage_monitor_push_port, connected_event,
                        image_saved_fn, event_queue, debug=False):
    monitor_socket = PullSocket(storage_monitor_push_port)
    connected_event.set()
    callback = None
    if image_saved_fn is not None:
        params = signature(image_saved_fn).parameters
        if len(params) == 2:
            callback = image_saved_fn
        elif len(params) == 3:
            callback = lambda axes, dataset: image_saved_fn(axes, dataset, event_queue)
        else:
            raise Exception('Image saved callbacks must have either 2 or three parameters')

    while True:
        try:
            message = monitor_socket.receive()
            if "finished" in message:
                # Poison, time to shut down
                monitor_socket.close()
                return

            index_entry = message["index_entry"]
            axes = dataset._add_index_entry(index_entry)
            dataset._new_image_arrived = True
            if callback is not None:
                callback(axes, dataset)
        except Exception as e:
            acquisition.abort(e)



class Acquisition(object, metaclass=NumpyDocstringInheritanceMeta):
    """
    Base class for Pycro-Manager acquisitions
    """

    def __init__(
        self,
        directory: str=None,
        name: str=None,
        image_process_fn : callable=None,
        event_generation_hook_fn: callable=None,
        pre_hardware_hook_fn: callable=None,
        post_hardware_hook_fn: callable=None,
        post_camera_hook_fn: callable=None,
        show_display: bool=True,
        napari_viewer=None,
        image_saved_fn: callable=None,
        process: bool=False,
        saving_queue_size: int=20,
        timeout: int=500,
        port: int=DEFAULT_PORT,
        debug: int=False,
        core_log_debug: int=False,
    ):
        """
        Parameters
        ----------
        directory : str
            saving directory for this acquisition. Required unless an image process function will be
            implemented that diverts images from saving
        name : str
            Saving name for the acquisition. Required unless an image process function will be
            implemented that diverts images from saving
        image_process_fn : Callable
            image processing function that will be called on each image that gets acquired.
            Can either take two arguments (image, metadata) where image is a numpy array and metadata is a dict
            containing the corresponding image metadata. Or a three argument version is accepted, which accepts (image,
            metadata, queue), where queue is a Queue object that holds upcoming acquisition events. The function
            should return either an (image, metadata) tuple or a list of such tuples
        event_generation_hook_fn : Callable
            hook function that will as soon as acquisition events are generated (before hardware sequencing optimization
            in the acquisition engine. This is useful if one wants to modify acquisition events that they didn't generate
            (e.g. those generated by a GUI application). Accepts either one argument (the current acquisition event)
            or two arguments (current event, event_queue)
        pre_hardware_hook_fn : Callable
            hook function that will be run just before the hardware is updated before acquiring
            a new image. In the case of hardware sequencing, it will be run just before a sequence of instructions are
            dispatched to the hardware. Accepts either one argument (the current acquisition event) or two arguments
            (current event, event_queue)
        post_hardware_hook_fn : Callable
            hook function that will be run just before the hardware is updated before acquiring
            a new image. In the case of hardware sequencing, it will be run just after a sequence of instructions are
            dispatched to the hardware, but before the camera sequence has been started. Accepts either one argument
            (the current acquisition event) or two arguments (current event, event_queue)
        post_camera_hook_fn : Callable
            hook function that will be run just after the camera has been triggered to snapImage or
            startSequence. A common use case for this hook is when one want to send TTL triggers to the camera from an
            external timing device that synchronizes with other hardware. Accepts either one argument (the current
            acquisition event) or two arguments (current event, event_queue)
        show_display : bool
            If True, show the image viewer window. If False, show no viewer.
        napari_viewer : napari.Viewer
            Provide a napari viewer to display acquired data in napari (https://napari.org/) rather than the built-in
            NDViewer. None by default. Data is added to the 'pycromanager acquisition' layer, which may be pre-configured by
            the user
        image_saved_fn : Callable
            function that takes two arguments (the Axes of the image that just finished saving, and the Dataset)
            or three arguments (Axes, Dataset and the event_queue) and gets called whenever a new image is written to
            disk
        process : bool
            Use multiprocessing instead of multithreading for acquisition hooks and image
            processors. This can be used to speed up CPU-bounded processing by eliminating bottlenecks
            caused by Python's Global Interpreter Lock, but also creates complications on Windows-based
            systems
        saving_queue_size : int
            The number of images to queue (in memory) while waiting to write to disk. Higher values should
            in theory allow sequence acquisitions to go faster, but requires the RAM to hold images while
            they are waiting to save
        timeout :
            Timeout in ms for connecting to Java side
        port :
            Allows overriding the defualt port for using Java side servers on a different port
        debug : bool
            whether to print debug messages
        core_log_debug : bool
            Print debug messages on java side in the micro-manager core log
        """
        self._debug = debug
        self._dataset = None
        self._finished = False
        self._exception = None
        self._port = port
        self._timeout = timeout
        self._nd_viewer = None
        self._napari_viewer = None

        # Get a dict of all named argument values (or default values when nothing provided)
        arg_names = [k for k in signature(Acquisition.__init__).parameters.keys() if k != 'self']
        l = locals()
        named_args = {arg_name: (l[arg_name] if arg_name in l else
                                     dict(signature(Acquisition.__init__).parameters.items())[arg_name].default)
                                     for arg_name in arg_names }

        if directory is not None:
            # Expend ~ in path
            directory = os.path.expanduser(directory)
            # If path is relative, retain knowledge of the current working directory
            named_args['directory'] = os.path.abspath(directory)

        self._create_event_queue(**named_args)
        self._create_remote_acquisition(**named_args)
        self._initialize_image_processor(**named_args)
        self._initialize_hooks(**named_args)

        # Acquistiion.start is now deprecated, so this can be removed later
        # Acquisitions now get started automatically when the first events submitted
        # but Magellan acquisitons (and probably others that generate their own events)
        # will need some new method to submit events only after image processors etc have been added
        self._remote_acq.start()
        self._dataset_disk_location = (
            self._remote_acq.get_data_sink().get_storage().get_disk_location()
            if self._remote_acq.get_data_sink() is not None
            else None
        )

        self._start_events()

        # Load remote storage
        data_sink = self._remote_acq.get_data_sink()
        if data_sink is not None:
            # load a view of the dataset in progress. This is used so that acq.get_dataset() can be called
            # while the acquisition is still running, and (optionally )so that a image_saved_fn can be called
            # when images are written to disk
            ndtiff_storage = data_sink.get_storage()
            summary_metadata = ndtiff_storage.get_summary_metadata()
            self._remote_storage_monitor = JavaObject('org.micromanager.remote.RemoteStorageMonitor', port=self._port)
            ndtiff_storage.add_image_written_listener(self._remote_storage_monitor)
            self._dataset = Dataset(dataset_path=self._dataset_disk_location, _summary_metadata=summary_metadata)
            # Monitor image arrival so they can be loaded on python side, but with no callback function
            # Need to do this regardless of whether you use it, so that it signals to shut down on Java side
            self._storage_monitor_thread = self._add_storage_monitor_fn(callback_fn=image_saved_fn, debug=self._debug)

        if show_display:
            if napari_viewer is None:
                # using NDViewer
                self._nd_viewer = self._remote_acq.get_data_sink().get_viewer()
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


    ########  Public API ###########
    def get_dataset(self):
        """
        Get access to the dataset backing this acquisition. If the acquisition is in progress,
        return a Dataset object that wraps the java class containing it. If the acquisition is finished,
        load the dataset from disk on the Python side for better performance
        """
        if self._finished:
            if self._dataset is None:
                self._dataset = Dataset(self._dataset_disk_location)

        return self._dataset

    def mark_finished(self):
        """
        Signal to acquisition that no more events will be added and it is time to initiate shutdown.
        This is only needed if the context manager (i.e. "with Acquisition...") is not used.
        """
        # Some acquisition types (e.g. Magellan) generate their own events
        # and don't send events over a port
        if self._event_queue is not None:
            # this should shut down storage and viewer as apporpriate
            self._event_queue.put(None)

    def await_completion(self):
        """Wait for acquisition to finish and resources to be cleaned up"""
        while not self._remote_acq.are_events_finished() or (
                self._remote_acq.get_data_sink() is not None and not self._remote_acq.get_data_sink().is_finished()):
            time.sleep(1 if self._debug else 0.05)
            self._check_for_exceptions()

        # Wait on all the other threads to shut down properly
        if hasattr(self, '_storage_monitor_thread'):
            self._storage_monitor_thread.join()
            # now that the shutdown signal has been received from the monitor,
            # tell it it is okay to shutdown its push socket
            self._remote_storage_monitor.storage_monitoring_complete()

        for hook_thread in self._hook_threads:
            hook_thread.join()

        if hasattr(self, '_event_thread'):
            self._event_thread.join()

        self._remote_acq = None
        self._finished = True

    def acquire(self, event_or_events: dict or list):
        """Submit an event or a list of events for acquisition. Optimizations (i.e. taking advantage of
        hardware synchronization, where available), will take place across this list of events, but not
        over multiple calls of this method. A single event is a python dictionary with a specific structure

        Parameters
        ----------
        event_or_events  : list, dict
            A single acquistion event (a dict) or a list of acquisition events

        """
        if event_or_events is None:
            # manual shutdown
            self._event_queue.put(None)
            return

        _validate_acq_events(event_or_events)
        self._event_queue.put(event_or_events)

    def abort(self, exception=None):
        """
        Cancel any pending events and shut down immediately

        Parameters
        ----------
        exception  : Exception
            The exception that is the reason abort is being called
        """
        # Store the exception that caused this
        if exception is not None:
            self._exception = exception

        # Clear any pending events on the python side, if applicable
        if self._event_queue is not None:
            self._event_queue.queue.clear()
            # Ensure that event queue gets shut down properly by adding this shutdown signal
            # The Java side cant shut this down because it is upstream of the remote acquisition
            self._event_queue.put(None)
        self._remote_acq.abort()

    def get_viewer(self):
        """
        Return a reference to the current viewer, if the show_display argument
        was set to True. The returned object is either an instance of NDViewer or napari.Viewer()
        """
        if self._napari_viewer is None:
            return self._nd_viewer
        else:
            return self._napari_viewer

    ########  Context manager (i.e. "with Acquisition...") ###########
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mark_finished()
        # now wait on it to finish
        self.await_completion()

    ########  Private methods ###########

    def _add_storage_monitor_fn(self, callback_fn=None, debug=False):
        """
        Add a callback function that gets called whenever a new image is writtern to disk (for acquisitions in
        progress only)

        Parameters
        ----------
        callback_fn : Callable
            callable with that takes 1 argument, the axes dict of the image just written
        """
        connected_event = threading.Event()

        push_port = self._remote_storage_monitor.get_port()
        monitor_thread = threading.Thread(
            target=_storage_monitor_fn,
            args=(
                self,
                self.get_dataset(),
                push_port,
                connected_event,
                callback_fn,
                self._event_queue,
                debug,
            ),
            name="ImageSavedCallbackThread",
        )

        monitor_thread.start()

        # Wait for pulling to start before you signal for pushing to start
        connected_event.wait()  # wait for push/pull sockets to connect

        # start pushing out all the image written events (including ones that have already accumulated)
        self._remote_storage_monitor.start()
        return monitor_thread

    def _check_for_exceptions(self):
        """
        Check for exceptions on the python side (i.e. hooks and processors)
        or on the Java side (i.e. hardware control)
        """
        # these will throw exceptions
        self._remote_acq.check_for_exceptions()
        if self._exception is not None:
            raise self._exception

    def _start_events(self, **kwargs):

        self.event_port = self._remote_acq.get_event_port()

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
            self._remote_acq.add_image_processor(java_processor)
            self._processor_thread = self._start_processor(
                java_processor, kwargs['image_process_fn'],
                # Some acquisitions (e.g. Explore acquisitions) create events on Java side
                self._event_queue if hasattr(self, '_event_queue') else None,
                process=kwargs['process'])


    def _initialize_hooks(self, **kwargs):
        self._hook_threads = []
        if kwargs['event_generation_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['event_generation_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.EVENT_GENERATION_HOOK)
        if kwargs['pre_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook,
                                            kwargs['pre_hardware_hook_fn'], self._event_queue,
                                                       process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.BEFORE_HARDWARE_HOOK)
        if kwargs['post_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_hardware_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_HARDWARE_HOOK)
        if kwargs['post_camera_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._port, args=[self._remote_acq],
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_camera_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_CAMERA_HOOK)


    def _create_event_queue(self, **kwargs):
        # Create thread safe queue for events so they can be passed from multiple processes
        self._event_queue = multiprocessing.Queue() if kwargs['process'] else queue.Queue()

    def _create_remote_acquisition(self, **kwargs):
        core = Core(port=self._port, timeout=self._timeout, debug=self._debug)
        acq_factory = JavaObject("org.micromanager.remote.RemoteAcquisitionFactory",
            port=self._port, args=[core], debug=self._debug)
        show_viewer = kwargs['show_display'] is True and\
                      kwargs['napari_viewer'] is None and\
                      (kwargs['directory'] is not None and kwargs['name'] is not None)

        self._remote_acq = acq_factory.create_acquisition(
            kwargs['directory'],
            kwargs['name'],
            show_viewer,
            kwargs['saving_queue_size'],
            kwargs['core_log_debug'],
        )

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


class XYTiledAcquisition(Acquisition):
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
            process: bool=False,
            saving_queue_size: int=20,
            timeout: int=500,
            port: int=DEFAULT_PORT,
            debug: bool=False,
            core_log_debug: bool=False,
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
        core = Core(port=self._port, timeout=self._timeout)
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
            kwargs['core_log_debug'],
        )

class ExploreAcquisition(Acquisition):
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
            process: bool=False,
            saving_queue_size: int=20,
            timeout: int=500,
            port: int=DEFAULT_PORT,
            debug: bool=False,
            core_log_debug: bool=False,
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


class MagellanAcquisition(Acquisition):
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
            core_log_debug: bool=False,
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

def _validate_acq_events(events: dict or list):
    """
    Validate if supplied events are a dictionary or a list of dictionaries
    that contain valid events. Throw an exception if not

    Parameters
    ----------
    events : dict or list

    """
    if isinstance(events, dict):
        _validate_acq_dict(events)
    elif isinstance(events, list):
        if len(events) == 0:
            raise Exception('events list cannot be empty')
        for event in events:
            if isinstance(event, dict):
                _validate_acq_dict(event)
            else:
                raise Exception('events must be a dictionary or a list of dictionaries')
    else:
        raise Exception('events must be a dictionary or a list of dictionaries')

def _validate_acq_dict(event: dict):
    """
    Validate event dictionary, and raise an exception or supply a warning and fix it if something is incorrect

    Parameters
    ----------
    event : dict

    """
    if 'axes' not in event.keys():
        raise Exception('event dictionary must contain an \'axes\' key. This event will be ignored')
    if 'row' in event.keys():
        warnings.warn('adding \'row\' as a top level key in the event dictionary is deprecated and will be disallowed in '
                      'a future version. Instead, add \'row\' as a key in the \'axes\' dictionary')
        event['axes']['row'] = event['row']
    if 'col' in event.keys():
        warnings.warn('adding \'col\' as a top level key in the event dictionary is deprecated and will be disallowed in '
                      'a future version. Instead, add \'column\' as a key in the \'axes\' dictionary')
        event['axes']['column'] = event['col']

    # TODO check for the validity of other acquisition event fields, and make sure that there aren't unexpected
    #   other fields, to help users catch simple errors





