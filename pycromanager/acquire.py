import numpy as np
import multiprocessing
import threading
from inspect import signature
import copy
import types
import time
from pycromanager.core import deserialize_array, Bridge
from pycromanager.data import Dataset
import warnings
import os.path
import queue

### These functions outside class to prevent problems with pickling when running them in differnet process


def _event_sending_fn(event_port, event_queue, debug=False):
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
    bridge = Bridge(debug=debug)
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


def _acq_hook_startup_fn(pull_port, push_port, hook_connected_evt, event_queue, hook_fn, debug):
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
    bridge = Bridge(debug=debug)

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


def _processor_startup_fn(
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
    bridge = Bridge(debug=debug)
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


class Acquisition(object):
    """ """

    def __init__(
        self,
        directory=None,
        name=None,
        image_process_fn=None,
        event_generation_hook_fn=None,
        pre_hardware_hook_fn=None,
        post_hardware_hook_fn=None,
        post_camera_hook_fn=None,
        show_display=True,
        tile_overlap=None,
        max_multi_res_index=None,
        magellan_acq_index=None,
        magellan_explore=False,
        process=False,
        saving_queue_size=20,
        debug=False,
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
            metadata, bridge, queue), where bridge and queue are an instance of the pycromanager.acquire.Bridge
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
        tile_overlap : int or tuple of int
            If given, XY tiles will be laid out in a grid and multi-resolution saving will be
            actived. Argument can be a two element tuple describing the pixel overlaps between adjacent
            tiles. i.e. (pixel_overlap_x, pixel_overlap_y), or an integer to use the same overlap for both.
            For these features to work, the current hardware configuration must have a valid affine transform
            between camera coordinates and XY stage coordinates
        max_multi_res_index : int
            Maximum index to downsample to in multi-res pyramid mode (which is only active if a value for
            "tile_overlap" is passed in, or if running a Micro-Magellan acquisition). 0 is no downsampling,
            1 is downsampled up to 2x, 2 is downsampled up to 4x, etc. If not provided, it will be dynamically
            calculated and updated from data
        show_display : bool
            show the image viewer window
        magellan_acq_index : int
            run this acquisition using the settings specified at this position in the main
            GUI of micro-magellan (micro-manager plugin). This index starts at 0
        magellan_explore : bool
            Run a Micro-magellan explore acquisition
        process : bool
            Use multiprocessing instead of multithreading for acquisition hooks and image
            processors. This can be used to speed up CPU-bounded processing by eliminating bottlenecks
            caused by Python's Global Interpreter Lock, but also creates complications on Windows-based
            systems
        saving_queue_size : int
            The number of images to queue (in memory) while waiting to write to disk. Higher values should
            in theory allow sequence acquisitions to go faster, but requires the RAM to hold images while
            they are waiting to save
        debug : bool
            whether to print debug messages
        """
        self.bridge = Bridge(debug=debug)
        self._debug = debug
        self._dataset = None

        if directory is not None:
            # Expend ~ in path
            directory = os.path.expanduser(directory)
            # If path is relative, retain knowledge of the current working directory
            directory = os.path.abspath(directory)

        if magellan_acq_index is not None:
            magellan_api = self.bridge.get_magellan()
            self._remote_acq = magellan_api.create_acquisition(magellan_acq_index)
            self._event_queue = None
        elif magellan_explore:
            magellan_api = self.bridge.get_magellan()
            self._remote_acq = magellan_api.create_explore_acquisition()
            self._event_queue = None
        else:
            # Create thread safe queue for events so they can be passed from multiple processes
            self._event_queue = multiprocessing.Queue() if process else queue.Queue()
            core = self.bridge.get_core()
            acq_factory = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteAcquisitionFactory", args=[core]
            )

            show_viewer = show_display and (directory is not None and name is not None)
            if tile_overlap is None:
                # argument placeholders, these wont actually be used
                x_overlap = 0
                y_overlap = 0
            else:
                if type(tile_overlap) is tuple:
                    x_overlap, y_overlap = tile_overlap
                else:
                    x_overlap = tile_overlap
                    y_overlap = tile_overlap

            self._remote_acq = acq_factory.create_acquisition(
                directory,
                name,
                show_viewer,
                tile_overlap is not None,
                x_overlap,
                y_overlap,
                max_multi_res_index if max_multi_res_index is not None else -1,
                saving_queue_size,
                debug,
            )
        storage = self._remote_acq.get_data_sink()
        if storage is not None:
            self.disk_location = storage.get_disk_location()

        if image_process_fn is not None:
            processor = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteImageProcessor"
            )
            self._remote_acq.add_image_processor(processor)
            self._start_processor(processor, image_process_fn, self._event_queue, process=process)

        if event_generation_hook_fn is not None:
            hook = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteAcqHook", args=[self._remote_acq]
            )
            self._start_hook(hook, event_generation_hook_fn, self._event_queue, process=process)
            self._remote_acq.add_hook(hook, self._remote_acq.EVENT_GENERATION_HOOK)
        if pre_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteAcqHook", args=[self._remote_acq]
            )
            self._start_hook(hook, pre_hardware_hook_fn, self._event_queue, process=process)
            self._remote_acq.add_hook(hook, self._remote_acq.BEFORE_HARDWARE_HOOK)
        if post_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteAcqHook", args=[self._remote_acq]
            )
            self._start_hook(hook, post_hardware_hook_fn, self._event_queue, process=process)
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_HARDWARE_HOOK)
        if post_camera_hook_fn is not None:
            hook = self.bridge.construct_java_object(
                "org.micromanager.remote.RemoteAcqHook", args=[self._remote_acq]
            )
            self._start_hook(hook, post_camera_hook_fn, self._event_queue, process=process)
            self._remote_acq.add_hook(hook, self._remote_acq.AFTER_CAMERA_HOOK)

        self._remote_acq.start()

        if magellan_acq_index is None and not magellan_explore:
            self.event_port = self._remote_acq.get_event_port()

            self.event_process = threading.Thread(
                target=_event_sending_fn,
                args=(self.event_port, self._event_queue, self._debug),
                name="Event sending",
            )
            self.event_process.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._event_queue is not None:  # magellan acquisitions dont have this
            # this should shut down storage and viewer as apporpriate
            self._event_queue.put(None)
        # now wait on it to finish
        self.await_completion()

    def get_disk_location(self):
        """
        Return the path where the dataset is on disk
        """
        return self._remote_acq.get_storage().get_disk_location()

    def get_dataset(self):
        """ """
        if self._dataset is None:
            self._dataset = Dataset(remote_storage=self._remote_acq.get_storage())
        return self._dataset

    def await_completion(self):
        """Wait for acquisition to finish and resources to be cleaned up"""
        while not self._remote_acq.is_finished():
            time.sleep(0.1)

    def acquire(self, events, keep_shutter_open=False):
        """Submit an event or a list of events for acquisition. Optimizations (i.e. taking advantage of
        hardware synchronization, where available), will take place across this list of events, but not
        over multiple calls of this method. A single event is a python dictionary with a specific structure

        Parameters
        ----------
        events

        keep_shutter_open :
             (Default value = False)

        Returns
        -------


        """
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

    def _start_hook(self, remote_hook, remote_hook_fn, event_queue, process):
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
            target=_acq_hook_startup_fn,
            name="AcquisitionHook",
            args=(
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

        self.processor_thread = (multiprocessing.Process if process else threading.Thread)(
            target=_processor_startup_fn,
            args=(
                pull_port,
                push_port,
                sockets_connected_evt,
                process_fn,
                event_queue,
                self._debug,
            ),
            name="ImageProcessor",
        )
        self.processor_thread.start()

        sockets_connected_evt.wait()  # wait for push/pull sockets to connect
        processor.start_push()


def multi_d_acquisition_events(
    num_time_points=1,
    time_interval_s=0,
    z_start=None,
    z_end=None,
    z_step=None,
    channel_group=None,
    channels=None,
    channel_exposures_ms=None,
    xy_positions=None,
    xyz_positions=None,
    order="tpcz",
    keep_shutter_open_between_channels=False,
    keep_shutter_open_between_z_steps=False,
):
    """Convenience function for generating the events of a typical multi-dimensional acquisition (i.e. an
    acquisition with some combination of multiple timepoints, channels, z-slices, or xy positions)

    Parameters
    ----------
    num_time_points : int
        How many time points if it is a timelapse (Default value = 1)
    time_interval_s : float
        the minimum interval between consecutive time points in seconds. Keep at 0 to go as
        fast as possible (Default value = 0)
    z_start : float
        z-stack starting position, in µm. If xyz_positions is given z_start is relative
        to the points' z position. (Default value = None)
    z_end : float
        z-stack ending position, in µm. If xyz_positions is given z_start is
        relative to the points' z position. (Default value = None)
    z_step : float
        step size of z-stack, in µm (Default value = None)
    channel_group : str
        name of the channel group (which should correspond to a config group in micro-manager) (Default value = None)
    channels : list of strings
        list of channel names, which correspond to possible settings of the config group
        (e.g. ['DAPI', 'FITC']) (Default value = None)
    channel_exposures_ms : list of floats or ints
        list of camera exposure times corresponding to each channel. The length of this list
        should be the same as the the length of the list of channels (Default value = None)
    xy_positions : arraylike
        N by 2 array where N is the number of XY stage positions, and the 2 are the X and Y
        coordinates (Default value = None)
    xyz_positions : arraylike
        N by 3 array where N is the number of XY stage positions, and the 3 are the X, Y and Z coordinates.
        If passed then z_start, z_end, and z_step will be relative to the z_position in xyz_positions. (Default value = None)
    z_positions : arraylike
        The z_positions for each xy point. Either 1D (shape: (N,) ) to specify the center z position for each xy point,
        or 2D (shape: (N, n_z) ) to fully specify the xyz points.
        If z_positions is 1D and z_start, z_end and z_step are not None then relative
        z_positions will be created using np.arange(z_position + z_start, z_position + z_end, z_step)
    order : str
        string that specifies the order of different dimensions. Must have some ordering of the letters
        c, t, p, and z. For example, 'tcz' would run a timelapse where z stacks would be acquired at each channel in
        series. 'pt' would move to different xy stage positions and run a complete timelapse at each one before moving
        to the next (Default value = 'tpcz')
    keep_shutter_open_between_channels : bool
        don't close the shutter in between channels (Default value = False)
    keep_shutter_open_between_z_steps : bool
        don't close the shutter during steps of a z stack (Default value = False)

    Returns
    -------
    events : dict
    """
    if xy_positions is not None and xyz_positions is not None:
        raise ValueError(
            "xyz_positions and xy_positions are incompatible arguments that cannot be passed together"
        )
    order = order.lower()
    if "p" in order and "z" in order and order.index("p") > order.index("z"):
        raise ValueError(
            "This function requres that the xy position come earlier in the order than z"
        )
    has_zsteps = z_start is not None and z_step is not None and z_end is not None
    z_positions = None
    if xy_positions is not None:
        xy_positions = np.asarray(xy_positions)
        z_positions = None
    elif xyz_positions is not None:
        xyz_positions = np.asarray(xyz_positions)
        xy_positions = xyz_positions[:, :2]
        z_positions = xyz_positions[:, 2][:, None]

    if has_zsteps:
        z_rel = np.arange(z_start, z_end + z_step, z_step)
        if z_positions is None:
            z_positions = z_rel
            if xy_positions is not None:
                z_positions = np.broadcast_to(
                    z_positions, (xy_positions.shape[0], z_positions.shape[0])
                )
        else:
            pos = []
            for z in z_positions:
                pos.append(z + z_rel)
            z_positions = np.asarray(pos)

    def generate_events(event, order):
        if len(order) == 0:
            yield event
            return
        elif order[0] == "t" and num_time_points != 1:
            time_indices = np.arange(num_time_points)
            for time_index in time_indices:
                new_event = copy.deepcopy(event)
                new_event["axes"]["time"] = time_index
                if time_interval_s != 0:
                    new_event["min_start_time"] = time_index * time_interval_s
                yield generate_events(new_event, order[1:])
        elif order[0] == "z" and z_positions is not None:
            if "axes" in event and "position" in event["axes"]:
                zs = z_positions[event["axes"]["position"]]
            else:
                zs = z_positions

            for z_index, z in enumerate(zs):
                new_event = copy.deepcopy(event)
                new_event["axes"]["z"] = z_index
                new_event["z"] = z
                if keep_shutter_open_between_z_steps:
                    new_event["keep_shutter_open"] = True
                yield generate_events(new_event, order[1:])
        elif order[0] == "p" and xy_positions is not None:
            for p_index, xy in enumerate(xy_positions):
                new_event = copy.deepcopy(event)
                new_event["axes"]["position"] = p_index
                new_event["x"] = xy[0]
                new_event["y"] = xy[1]
                yield generate_events(new_event, order[1:])
        elif order[0] == "c" and channel_group is not None and channels is not None:
            for i in range(len(channels)):
                new_event = copy.deepcopy(event)
                new_event["channel"] = {"group": channel_group, "config": channels[i]}
                if channel_exposures_ms is not None:
                    new_event["exposure"] = i
                if keep_shutter_open_between_channels:
                    new_event["keep_shutter_open"] = True
                yield generate_events(new_event, order[1:])
        else:
            # this axis appears to be missing
            yield generate_events(event, order[1:])

    # collect all events into a single list
    base_event = {"axes": {}}
    events = []

    def appender(next):
        """

        Parameters
        ----------
        next :


        Returns
        -------

        """
        if isinstance(next, types.GeneratorType):
            for n in next:
                appender(n)
        else:
            events.append(next)

    appender(generate_events(base_event, order))
    return events
