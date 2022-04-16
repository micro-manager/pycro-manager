import subprocess
import platform
import atexit
from pycromanager.bridge import Bridge
from pycromanager.java_classes import Core
import copy
import types
import numpy as np
import gc


SUBPROCESSES = []

def cleanup():
    for p in SUBPROCESSES:
        p.terminate()

# make sure any Java processes are cleaned up when Python exits
atexit.register(cleanup)

def start_headless(
    mm_app_path: str, config_file: str=None, java_loc: str=None, core_log_path: str=None, buffer_size_mb: int=1024,
        port: int=Bridge.DEFAULT_PORT, timeout: int=5000, **core_kwargs
):
    """
    Start a Java process that contains the neccessary libraries for pycro-manager to run,
    so that it can be run independently of the Micro-Manager GUI/application. This calls
    will create and initialize MMCore with the configuration file provided.

    On windows plaforms, the Java Runtime Environment will be grabbed automatically
    as it is installed along with the Micro-Manager application.

    On non-windows platforms, it may need to be installed/specified manually in order to ensure compatibility.
    Installing Java 11 is the most likely version to work without issue

    Parameters
    ----------
    mm_app_path : str
        Path to top level folder of Micro-Manager installation (made with graphical installer)
    config_file : str
        Path to micro-manager config file, with which core will be initialized. If None then initialization
        is left to the user.
    java_loc: str
        Path to the java version that it should be run with
    core_log_path : str
        Path to where core log files should be created
    buffer_size_mb : int
        Size of circular buffer in MB in MMCore
    port : int
        Default port to use for ZMQServer
    timeout : int, default 5000
        Timeout for connection to server in milliseconds
    **core_kwargs
        Passed on to the Core constructor

    """

    classpath = mm_app_path + '/plugins/Micro-Manager/*'
    if java_loc is None:
        if platform.system() == "Windows":
            # windows comes with its own JRE
            java_loc = mm_app_path + "/jre/bin/javaw.exe"
        else:
            java_loc = "java"
    # This starts Java process and instantiates essential objects (core,
    # acquisition engine, ZMQServer)
    SUBPROCESSES.append(subprocess.Popen(
            [
                java_loc,
                "-classpath",
                classpath,
                "-Dsun.java2d.dpiaware=false",
                "-Xmx2000m",

                # This is used by MM desktop app but breaks things on MacOS...Don't think its neccessary
                # "-XX:MaxDirectMemorySize=1000",
                "org.micromanager.remote.HeadlessLauncher",
                str(port)
            ]
        )
    )

    # Initialize core
    core = Core(timeout=timeout, port=port, **core_kwargs)

    core.wait_for_system()
    if config_file is not None:
        core.load_system_configuration(config_file)
    core.set_circular_buffer_memory_footprint(buffer_size_mb)

    if core_log_path is not None:
        core.enable_stderr_log(True)
        core.enable_debug_log(True)
        core.set_primary_log_file(core_log_path)

    core = None
    gc.collect()




def multi_d_acquisition_events(
    num_time_points: int=1,
    time_interval_s: float=0,
    z_start: float=None,
    z_end: float=None,
    z_step: float=None,
    channel_group: str=None,
    channels: list=None,
    channel_exposures_ms: list=None,
    xy_positions=None,
    xyz_positions=None,
    order: str="tpcz",
    keep_shutter_open_between_channels: bool=False,
    keep_shutter_open_between_z_steps: bool=False,
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
                    new_event["exposure"] = channel_exposures_ms[i]
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



