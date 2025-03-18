from mmpycorex import create_core_instance, terminate_core_instances
from mmpycorex import Core
from pycromanager.acquisition.acq_eng_py.internal.engine import Engine
from pyjavaz import DEFAULT_BRIDGE_PORT
import atexit
import pymmcore
import types


def start_headless(
    mm_app_path: str, config_file: str=None, java_loc: str=None,
        python_backend=False, core_log_path: str='',
        buffer_size_mb: int=1024, max_memory_mb: int=2000,
        port: int=DEFAULT_BRIDGE_PORT, debug=False):
    """
    Start an instance of the Micro-Manager core and acquisition engine in headless mode. This can be
    either a Python (i.e. pymmcore) or Java (i.e. MMCoreJ) backend. If a Python backend is used,
    the core will be started in the same process.

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
    create_core_instance(
        mm_app_path=mm_app_path, config_file=config_file, java_loc=java_loc,
        python_backend=python_backend, core_log_path=core_log_path,
        buffer_size_mb=buffer_size_mb, max_memory_mb=max_memory_mb,
        port=port, debug=debug)
    if python_backend:
        Engine(Core())
    else:
        # make sure any Java processes are cleaned up when Python exits
        atexit.register(stop_headless)

def stop_headless(debug=False):
    terminate_core_instances(debug=debug)
    if Engine.get_instance():
        Engine.get_instance().shutdown()

