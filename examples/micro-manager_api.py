"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge
import numpy as np
import matplotlib.pyplot as plt

# #### Setup ####
# #establish communication with Magellan
# bridge = PygellanBridge(convert_camel_case=False)
#
# #Access an object in a micromanger plugin
# magellan = bridge.construct_java_object('org.micromanager.magellan.api.MagellanAPI')
#
# #get object representing micro-manager API
# studio = bridge.get_studio()
#
# #do some stuff
# a = studio.acquisitions()

from pygellan.acquire import PygellanBridge
bridge = PygellanBridge()
mm = bridge.get_studio()
mmc = bridge.get_core()
mmc.set_exposure("Camera", 100)
mmc.set_exposure(120)
pass

# while True:
#     mm.live().snap(True)
