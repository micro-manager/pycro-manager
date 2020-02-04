"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge
import numpy as np
import matplotlib.pyplot as plt

#### Setup ####
#establish communication with Magellan
bridge = PygellanBridge(convert_camel_case=False)

#Access an object in a micromanger plugin
magellan = bridge.construct_java_object_from_classpath('org.micromanager.magellan.api.MagellanAPI')

#get object representing micro-manager API
studio = bridge.get_studio()

#do some stuff
a = studio.acquisitions()

