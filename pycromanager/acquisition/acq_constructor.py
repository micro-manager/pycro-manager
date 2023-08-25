from pycromanager.headless import _PYMMCORES
from pycromanager.acquisition.java_backend_acquisitions import JavaBackendAcquisition
from pycromanager.acquisition.python_backend_acquisitions import PythonBackendAcquisition

class Acquisition:
    def __new__(cls, *args, **kwargs):
        if _PYMMCORES:
            # Python backend detected, so create a python backend acquisition
            return PythonBackendAcquisition(*args, **kwargs)
        else:
            return JavaBackendAcquisition(*args, **kwargs)
