from pycromanager.headless import _PYMMCORES
from pycromanager.acquisition.java_backend_acquisitions import JavaBackendAcquisition
from pycromanager.acquisition.python_backend_acquisitions import PythonBackendAcquisition
from pycromanager.acquisition.acquisition_superclass import Acquisition as PycromanagerAcquisitionBase
from inspect import signature

# This is a convenience class that automatically selects the appropriate acquisition
# type based on backend is running. It is subclassed from the base acquisition class
# so that it can inherit its docstrings. It cant be the parent class of it, or else
# there will be a circular import
class Acquisition(PycromanagerAcquisitionBase):
    def __new__(cls,
            directory: str = None,
            name: str = 'default_acq_name',
            image_process_fn: callable = None,
            event_generation_hook_fn: callable = None,
            pre_hardware_hook_fn: callable = None,
            post_hardware_hook_fn: callable = None,
            post_camera_hook_fn: callable = None,
            notification_callback_fn: callable = None,
            image_saved_fn: callable = None,
            napari_viewer=None,
            debug: int = False,
                **kwargs):
        # package up all the arguments
        arg_names = [k for k in signature(Acquisition.__init__).parameters.keys() if k != 'self']
        l = locals()
        named_args = {arg_name: (l[arg_name] if arg_name in l else
                                     dict(signature(Acquisition.__init__).parameters.items())[arg_name].default)
                                     for arg_name in arg_names }

        if _PYMMCORES:
            # Python backend detected, so create a python backend acquisition
            specific_arg_names = [k for k in signature(JavaBackendAcquisition.__init__).parameters.keys() if k != 'self']
            for name in specific_arg_names:
                if name in kwargs:
                    named_args[name] = kwargs[name]
            return PythonBackendAcquisition(**named_args)
        else:
            # add any kwargs are specific to java backend
            specific_arg_names = [k for k in signature(JavaBackendAcquisition.__init__).parameters.keys() if k != 'self']
            for name in specific_arg_names:
                if name in kwargs:
                    named_args[name] = kwargs[name]
            return JavaBackendAcquisition(**named_args)
