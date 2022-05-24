import numpy as np
import multiprocessing
import threading
from inspect import signature
import time
from pycromanager.bridge import deserialize_array, Bridge
from pycromanager.java_classes import Core, JavaObject, Magellan
from pycromanager.data import Dataset
import warnings
import os.path
import queue
from pycromanager.bridge import _JavaObjectShadow
from docstring_inheritance import NumpyDocstringInheritanceMeta


### These functions outside class to prevent problems with pickling when running them in differnet process


def _run_acq_event_source(bridge_port, bridge_timeout, event_port, event_queue, debug=False):
    """

    Parameters
    ----------
    event_port :

    event_queue :

    debug :
         (Default value = False)

    Returns
    -------

    """

    bridge = Bridge(debug=debug, port=bridge_port, timeout=bridge_timeout)
    event_socket = bridge._connect_push(event_port)
    while True:
        events = event_queue.get(block=True)
        if debug:
            print("got event(s):", events)
        if events is None:
            # Poison, time to shut down
            event_socket.send({"events": [{"special": "acquisition-end"}]})
            event_socket.close()
            return
        event_socket.send({"events": events if type(events) == list else [events]})
        if debug:
            print("sent events")

def _run_acq_hook(bridge_port, bridge_timeout, pull_port, push_port, hook_connected_evt, event_queue, hook_fn, debug=False):
    """

    Parameters
    ----------
    pull_port :

    push_port :

    hook_connected_evt :

    event_queue :

    hook_fn :

    debug :


    Returns
    -------

    """
    bridge = Bridge(debug=debug, port=bridge_port, timeout=bridge_timeout)

    push_socket = bridge._connect_push(pull_port)
    pull_socket = bridge._connect_pull(push_port)
    hook_connected_evt.set()

    while True:
        event_msg = pull_socket.receive()

        if "special" in event_msg and event_msg["special"] == "acquisition-end":
            push_socket.send({})
            push_socket.close()
            pull_socket.close()
            return
        else:
            if "events" in event_msg.keys():
                event_msg = event_msg["events"]  # convert from sequence
            params = signature(hook_fn).parameters
            if len(params) == 1 or len(params) == 3:
                try:
                    if len(params) == 1:
                        new_event_msg = hook_fn(event_msg)
                    elif len(params) == 3:
                        new_event_msg = hook_fn(event_msg, bridge, event_queue)
                except Exception as e:
                    warnings.warn("exception in acquisition hook: {}".format(e))
                    continue
            else:
                raise Exception("Incorrect number of arguments for hook function. Must be 1 or 3")

        if isinstance(new_event_msg, list):
            new_event_msg = {
                "events": new_event_msg
            }  # convert back to the expected format for a sequence
        push_socket.send(new_event_msg)


def _run_image_processor(
        bridge_port, bridge_timeout,
        pull_port, push_port, sockets_connected_evt, process_fn, event_queue, debug
):
    """

    Parameters
    ----------
    pull_port :

    push_port :

    sockets_connected_evt :

    process_fn :

    event_queue :

    debug :


    Returns
    -------

    """
    bridge = Bridge(debug=debug, port=bridge_port, timeout=bridge_timeout)
    push_socket = bridge._connect_push(pull_port)
    pull_socket = bridge._connect_pull(push_port)
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
            raise Exception("If image is returned, it must be of the form (pixel, metadata)")

        pixels = image_tags_tuple[0]
        metadata = image_tags_tuple[1]

        # only accepts same pixel type as original
        if not np.issubdtype(image_tags_tuple[0].dtype, original_dtype) and not np.issubdtype(
            original_dtype, image_tags_tuple[0].dtype
        ):
            raise Exception(
                "Processed image pixels must have same dtype as input image pixels, "
                "but instead they were {} and {}".format(image_tags_tuple[0].dtype, pixels.dtype)
            )

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
        push_socket.send(processed_img)

    while True:
        message = None
        while message is None:
            message = pull_socket.receive(timeout=30)  # check for new message

        if "special" in message and message["special"] == "finished":
            push_socket.send(message)  # Continue propagating the finihsed signal
            push_socket.close()
            pull_socket.close()
            return

        metadata = message["metadata"]
        pixels = deserialize_array(message["pixels"])
        if metadata['PixelType'] == 'RGB32':
            image = np.reshape(pixels, [metadata["Height"], metadata["Width"], 4])[..., :3]
        else:
            image = np.reshape(pixels, [metadata["Height"], metadata["Width"]])

        params = signature(process_fn).parameters
        if len(params) == 2 or len(params) == 4:
            processed = None
            try:
                if len(params) == 2:
                    processed = process_fn(image, metadata)
                elif len(params) == 4:
                    processed = process_fn(image, metadata, bridge, event_queue)
            except Exception as e:
                warnings.warn("exception in image processor: {}".format(e))
                continue
        else:
            raise Exception(
                "Incorrect number of arguments for image processing function, must be 2 or 4"
            )

        if processed is None:
            continue

        if type(processed) == list:
            for image in processed:
                process_and_sendoff(image, pixels.dtype)
        else:
            process_and_sendoff(processed, pixels.dtype)



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
        show_display: bool or str=True,
        image_saved_fn: callable=None,
        process: bool=False,
        saving_queue_size: int=20,
        bridge_timeout: int=500,
        port: int=Bridge.DEFAULT_PORT,
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
            containing the corresponding iamge metadata. Or a 4 argument version is accepted, which accepts (image,
            metadata, bridge, queue), where bridge and queue are an instance of the pycromanager.bridge.Bridge
            object for the purposes of interacting with arbitrary code on the Java side (such as the micro-manager
            core), and queue is a Queue objects that holds upcomning acquisition events. Both version must either
            return
        event_generation_hook_fn : Callable
            hook function that will as soon as acquisition events are generated (before hardware sequencing optimization
            in the acquisition engine. This is useful if one wants to modify acquisition events that they didn't generate
            (e.g. those generated by a GUI application). Accepts either one argument (the current acquisition event)
            or three arguments (current event, bridge, event Queue)
        pre_hardware_hook_fn : Callable
            hook function that will be run just before the hardware is updated before acquiring
            a new image. In the case of hardware sequencing, it will be run just before a sequence of instructions are
            dispatched to the hardware. Accepts either one argument (the current acquisition event) or three arguments
            (current event, bridge, event Queue)
        post_hardware_hook_fn : Callable
            hook function that will be run just before the hardware is updated before acquiring
            a new image. In the case of hardware sequencing, it will be run just after a sequence of instructions are
            dispatched to the hardware, but before the camera sequence has been started. Accepts either one argument
            (the current acquisition event) or three arguments (current event, bridge, event Queue)
        post_camera_hook_fn : Callable
            hook function that will be run just after the camera has been triggered to snapImage or
            startSequence. A common use case for this hook is when one want to send TTL triggers to the camera from an
            external timing device that synchronizes with other hardware. Accepts either one argument (the current
            acquisition event) or three arguments (current event, bridge, event Queue)
        show_display : bool or str
            If True, show the image viewer window. If False, show no viewer. If 'napari', show napari as the viewer
        image_saved_fn : Callable
            function that takes two arguments (the Axes of the image that just finished saving, and the Dataset)
            and gets called whenever a new image is written to disk
        process : bool
            Use multiprocessing instead of multithreading for acquisition hooks and image
            processors. This can be used to speed up CPU-bounded processing by eliminating bottlenecks
            caused by Python's Global Interpreter Lock, but also creates complications on Windows-based
            systems
        saving_queue_size : int
            The number of images to queue (in memory) while waiting to write to disk. Higher values should
            in theory allow sequence acquisitions to go faster, but requires the RAM to hold images while
            they are waiting to save
        bridge_timeout :
            Timeout in ms of all operations going throught the Bridge
        port :
            Allows overriding the defualt port for using Java side servers on a different port
        debug : bool
            whether to print debug messages
        core_log_debug : bool
            Print debug messages on java side in the micro-manager core log
        """
        self._bridge_timeout = bridge_timeout
        self.bridge = Bridge(debug=debug, port=port, timeout=bridge_timeout)
        self._bridge_port = port
        self._debug = debug
        self._dataset = None
        self._finished = False

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

        self._remote_acq.start()
        self._dataset_disk_location = (
            self._remote_acq.get_storage().get_disk_location()
            if self._remote_acq.get_storage() is not None
            else None
        )

        self._start_events()

        # Load remote storage
        self._dataset = Dataset(remote_storage_monitor=self._remote_acq.get_storage_monitor())
        if image_saved_fn is not None:
            self._storage_monitor_thread = self._dataset._add_storage_monitor_fn(
                callback_fn=image_saved_fn, debug=self._debug
            )
        else:
            # Monitor image arrival so they can be loaded on python side, but with no callback function
            # Need to do this regardless of whether you use it, so that it signals to shut down on Java side
            self._storage_monitor_thread = self._dataset._add_storage_monitor_fn(callback_fn=None, debug=self._debug)


        if show_display == 'napari':
            import napari
            from pycromanager.napari_util import start_napari_signalling
            viewer = napari.Viewer()
            start_napari_signalling(viewer, self.get_dataset())



    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mark_finished()
        # now wait on it to finish
        self.await_completion()


    def _start_events(self, **kwargs):

        self.event_port = self._remote_acq.get_event_port()

        self._event_thread = threading.Thread(
            target=_run_acq_event_source,
            args=(self._bridge_port, self._bridge_timeout, self.event_port, self._event_queue, self._debug),
            name="Event sending",
        )
        self._event_thread.start()

    def _initialize_image_processor(self, **kwargs):

        if kwargs['image_process_fn'] is not None:
            java_processor = JavaObject(
                "org.micromanager.remote.RemoteImageProcessor", port=self._bridge_port
            )
            self._remote_acq.add_image_processor(java_processor)
            self._processor_thread = self._start_processor(
                java_processor, kwargs['image_process_fn'], self._event_queue, process=kwargs['process'])


    def _initialize_hooks(self, **kwargs):
        self._hook_threads = []
        if kwargs['event_generation_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._bridge_port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['event_generation_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.EVENT_GENERATION_HOOK)
        if kwargs['pre_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._bridge_port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook,
                                            kwargs['pre_hardware_hook_fn'], self._event_queue,
                                                       process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.BEFORE_HARDWARE_HOOK)
        if kwargs['post_hardware_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._bridge_port, args=[self._remote_acq]
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_hardware_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_HARDWARE_HOOK)
        if kwargs['post_camera_hook_fn'] is not None:
            hook = JavaObject(
                "org.micromanager.remote.RemoteAcqHook", port=self._bridge_port, args=[self._remote_acq],
            )
            self._hook_threads.append(self._start_hook(hook, kwargs['post_camera_hook_fn'],
                                                       self._event_queue, process=kwargs['process']))
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_CAMERA_HOOK)


    def _create_event_queue(self, **kwargs):
        # Create thread safe queue for events so they can be passed from multiple processes
        self._event_queue = multiprocessing.Queue() if kwargs['process'] else queue.Queue()

    def _create_remote_acquisition(self, **kwargs):
        core = Core(port= self._bridge_port, timeout=self._bridge_timeout)
        acq_factory = JavaObject(
            "org.micromanager.remote.RemoteAcquisitionFactory", port=self._bridge_port, args=[core]
        )
        show_viewer = kwargs['show_display'] == True and (kwargs['directory'] is not None and kwargs['name'] is not None)

        self._remote_acq = acq_factory.create_acquisition(
            kwargs['directory'],
            kwargs['name'],
            show_viewer,
            kwargs['saving_queue_size'],
            kwargs['core_log_debug'],
        )


    def get_dataset(self):
        """
        Get access to the dataset backing this acquisition. If the acquisition is in progress,
        return a Dataset object that wraps the java class containing it. If the acquisition is finished,
        load the dataset from disk on the Python side for better performance
        """
        if self._finished:
            if self._dataset is None or self._dataset._remote_storage_monitor is not None:
                self._dataset = Dataset(self._dataset_disk_location)

        return self._dataset

    def mark_finished(self):
        """
        Signal to acquisition that no more events will be added and it is time to initiate shutdown.
        This is only needed if the context manager (i.e. "with Acquisition...") is not used
        """
        if self._event_queue is not None:  # magellan acquisitions dont have this
            # this should shut down storage and viewer as apporpriate
            self._event_queue.put(None)

    def await_completion(self):
        """Wait for acquisition to finish and resources to be cleaned up"""
        while not self._remote_acq.is_finished():
            time.sleep(0.01)
            self._remote_acq.check_for_exceptions()
        self._remote_acq = None

        # Wait on all the other threads to shut down properly
        self._storage_monitor_thread.join()

        for hook_thread in self._hook_threads:
            hook_thread.join()

        if hasattr(self, '_event_thread'):
            self._event_thread.join()

        self._finished = True

    def acquire(self, events: dict or list, keep_shutter_open=False):
        """Submit an event or a list of events for acquisition. Optimizations (i.e. taking advantage of
        hardware synchronization, where available), will take place across this list of events, but not
        over multiple calls of this method. A single event is a python dictionary with a specific structure

        Parameters
        ----------
        events  : list, dict
            A single acquistion event (a dict) or a list of acquisition events
        keep_shutter_open :
             (Default value = False)

        Returns
        -------


        """
        if events is None:
            # manual shutdown
            self._event_queue.put(None)
            return
        if keep_shutter_open and isinstance(events, list):
            for e in events:
                e["keep_shutter_open"] = True
            events.append(
                {"keep_shutter_open": False}
            )  # return to autoshutter, dont acquire an image
        elif keep_shutter_open and isinstance(events, dict):
            events["keep_shutter_open"] = True
            events = [
                events,
                {"keep_shutter_open": False},
            ]  # return to autoshutter, dont acquire an image
        self._event_queue.put(events)

    def _start_hook(self, remote_hook : _JavaObjectShadow, remote_hook_fn : callable, event_queue, process):
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
                self._bridge_port,
                self._bridge_timeout,
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
                self._bridge_port,
                self._bridge_timeout,
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
            bridge_timeout: int=500,
            port: int=Bridge.DEFAULT_PORT,
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
        # Collct all argument values except the ones specific to Magellan
        arg_names = list(signature(self.__init__).parameters.keys())
        arg_names.remove('tile_overlap')
        arg_names.remove('max_multi_res_index')
        l = locals()
        named_args = {arg_name: l[arg_name] for arg_name in arg_names}
        super().__init__(**named_args)

    def _create_remote_acquisition(self, port, timeout, **kwargs):
        core = Core(port=self._bridge_port, timeout=self._bridge_timeout)
        acq_factory = JavaObject(
            "org.micromanager.remote.RemoteAcquisitionFactory", port=self._bridge_port, args=[core]
        )

        show_viewer = kwargs['show_display'] and (kwargs['directory'] is not None and kwargs['name'] is not None)
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
            bridge_timeout: int=500,
            port: int=Bridge.DEFAULT_PORT,
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
        if self.magellan_acq_index is not None:
            magellan_api = Magellan()
            self._remote_acq = magellan_api.create_acquisition(self.magellan_acq_index)
            self._event_queue = None
        elif self.magellan_explore:
            magellan_api = Magellan()
            self._remote_acq = magellan_api.create_explore_acquisition()
            self._event_queue = None
