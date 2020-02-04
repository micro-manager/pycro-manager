"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge
import numpy as np
import matplotlib.pyplot as plt

#### Setup ####
#establish communication with Magellan
bridge = PygellanBridge(convert_camel_case=False)
#get object representing micro-manager API
studio = bridge.get_studio()

#do some stuff
a = studio.acquisitions()

