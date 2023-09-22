import subprocess
import platform
import atexit
import threading
import types

from pycromanager.acquisition.acq_eng_py.internal.engine import Engine
from pycromanager.zmq_bridge.bridge import _Bridge, server_terminated
from pymmcore import CMMCore
import pymmcore

import re

class TaggedImage:

    def __init__(self, tags, pix):
        self.tags = tags
        self.pix = pix

def _camel_to_snake(name):
    """
    Convert camelCase string to snake_case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def _create_pymmcore_instance():
    """
    Make a subclass of CMMCore with two differences:

    1. All methods are converted to snake_case
    2. add convenience methods to match the MMCoreJ API:
    """

    # Create a new dictionary for the class attributes
    new_attributes = {}

    # Iterate through the original attributes
    for attr_name, attr_value in vars(CMMCore).items():
        # If it's a dunder method, skip it (we don't want to override these)
        if attr_name.startswith("__") and attr_name.endswith("__"):
            continue
        # If the attribute is callable (i.e., a method), convert its name to snake_case and add it
        if callable(attr_value):
            new_attr_name = _camel_to_snake(attr_name)
            new_attributes[new_attr_name] = attr_value

    # Create and return a new class that subclasses the original class and has the new attributes
    clz = type(CMMCore.__name__ + "SnakeCase", (CMMCore,), new_attributes)

    instance = clz()

    def pop_next_tagged_image(self):
        md = pymmcore.Metadata()
        pix = self.pop_next_image_md(0, 0, md)
        tags = {key: md.GetSingleTag(key).GetValue() for key in md.GetKeys()}
        return TaggedImage(tags, pix)

    def get_tagged_image(self, cam_index, camera, height, width, binning=None, pixel_type=None, roi_x_start=None,
                         roi_y_start=None):
        """
        Different signature than the Java version because of difference in metadata handling in the swig layers
        """
        pix = self.get_image()
        md = pymmcore.Metadata()
        # most of the same tags from pop_next_tagged_image, which may not be the same as the MMCoreJ version of this function
        tags = {'Camera': camera, 'Height': height, 'Width': width, 'PixelType': pixel_type,
                'CameraChannelIndex': cam_index}
        # Could optionally add these for completeness but there might be a performance hit
        if binning is not None:
            tags['Binning'] = binning
        if roi_x_start is not None:
            tags['ROI-X-start'] = roi_x_start
        if roi_y_start is not None:
            tags['ROI-Y-start'] = roi_y_start

        return TaggedImage(tags, pix)

    instance.get_tagged_image = types.MethodType(get_tagged_image, instance)
    instance.pop_next_tagged_image = types.MethodType(pop_next_tagged_image, instance)

    # attach TaggedImage class
    instance.TaggedImage = TaggedImage
    return instance


_JAVA_HEADLESS_SUBPROCESSES = []
_PYMMCORES = []

def stop_headless(debug=False):
    for p in _JAVA_HEADLESS_SUBPROCESSES:
        port = p.port
        if debug:
            print('Stopping headless process with pid {}'.format(p.pid))
        p.terminate()
        server_terminated(port)
        if debug:
            print('Waiting for process with pid {} to terminate'.format(p.pid))
        p.wait()  # wait for process to terminate
        if debug:
            print('Process with pid {} terminated'.format(p.pid))
    _JAVA_HEADLESS_SUBPROCESSES.clear()
    if debug:
        print('Stopping {} pymmcore instances'.format(len(_PYMMCORES)))
    for c in _PYMMCORES:
        if debug:
            print('Stopping pymmcore instance')
        c.unloadAllDevices()
        if debug:
            print('Unloaded all devices')
        Engine.get_instance().shutdown()
        if debug:
            print('Engine shut down')
    _PYMMCORES.clear()
    if debug:
        print('Headless stopped')

# make sure any Java processes are cleaned up when Python exits
atexit.register(stop_headless)

def start_headless(
    mm_app_path: str, config_file: str=None, java_loc: str=None,
        python_backend=False, core_log_path: str='',
        buffer_size_mb: int=1024, max_memory_mb: int=2000,
        port: int=_Bridge.DEFAULT_PORT, debug=False):
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
        Path to the java version that it should be run with (Java backend only)
    python_backend : bool
        Whether to use the python backend or the Java backend
    core_log_path : str
        Path to where core log files should be created
    buffer_size_mb : int
        Size of circular buffer in MB in MMCore
    max_memory_mb : int
        Maximum amount of memory to be allocated to JVM (Java backend only
    port : int
        Default port to use for ZMQServer (Java backend only)
    debug : bool
        Print debug messages
    """

    if python_backend:
        mmc = _create_pymmcore_instance()
        mmc.set_device_adapter_search_paths([mm_app_path])
        mmc.load_system_configuration(config_file)
        mmc.set_circular_buffer_memory_footprint(buffer_size_mb)
        _PYMMCORES.append(mmc) # Store so it doesn't get garbage collected
        Engine(mmc)
    else:
        classpath = mm_app_path + '/plugins/Micro-Manager/*'
        if java_loc is None:
            if platform.system() == "Windows":
                # windows comes with its own JRE
                java_loc = mm_app_path + "/jre/bin/javaw.exe"
            else:
                java_loc = "java"
        # This starts Java process and instantiates essential objects (core,
        # acquisition engine, ZMQServer)
        process = subprocess.Popen(
                [
                    java_loc,
                    "-classpath",
                    classpath,
                    "-Dsun.java2d.dpiaware=false",
                    f"-Xmx{max_memory_mb}m",
                    # This is used by MM desktop app but breaks things on MacOS...Don't think its neccessary
                    # "-XX:MaxDirectMemorySize=1000",
                    "org.micromanager.remote.HeadlessLauncher",
                    str(port),
                    config_file if config_file is not None else '',
                    str(buffer_size_mb),
                    core_log_path,
                ], cwd=mm_app_path, stdout=subprocess.PIPE
            )
        process.port = port
        _JAVA_HEADLESS_SUBPROCESSES.append(process)

        started = False
        output = True
        # Some drivers output various status messages which need to be skipped over to look for the STARTED token.
        while output and not started:
            output = process.stdout.readline()
            started = "STARTED" in output.decode('utf-8')
        if not started:
            raise Exception('Error starting headless mode')
        if debug:
            print('Headless mode started')
            def logger():
                while process in _JAVA_HEADLESS_SUBPROCESSES:
                    line = process.stdout.readline().decode('utf-8')
                    if line.strip() != '':
                        print(line)
            threading.Thread(target=logger).start()


