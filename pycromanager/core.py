from pycromanager.mm_java_classes import ZMQRemoteMMCoreJ
import pymmcore
from pycromanager.headless import _PYMMCORES

class Core():
    """
    Return a remote Java ZMQ Core, or a local Python Core, if the start_headless has been called with a Python backend
    """

    def __new__(cls, **kwargs):
        if _PYMMCORES:
            return _PYMMCORES[0]
        else:
            return ZMQRemoteMMCoreJ(**kwargs)

