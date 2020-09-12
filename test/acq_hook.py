from pycromanager import Acquisition, multi_d_acquisition_events
import numpy as np


#this hook function can control the micro-manager core
def hook_fn(event):

    return event

with Acquisition(directory='/Users/henrypinkard/megllandump', name='acquisition_name',
                  pre_hardware_hook_fn=hook_fn) as acq:
    acq.acquire(multi_d_acquisition_events(10))


