"""
This example shows how to use pygellan to interact with the micro-manager core. Aside from
the setup section, each following section can be run independently
"""
from pygellan.acquire import MagellanBridge
import numpy as np
import matplotlib.pyplot as plt

#### Setup ####
#establish communication with Magellan
bridge = MagellanBridge()
#get object representing micro-manager core
core = bridge.get_core()


#### Calling core functions ###
exposure = core.get_exposure()


#### Setting and getting properties ####
#Here we set a property of the core itself, but same code works for device properties
auto_shutter = core.get_property('Core', 'AutoShutter')
core.set_property('Core', 'AutoShutter', 0)


#### Acquiring images ####
#The micro-manager core exposes several mechanisms foor acquiring images. In order to not interfere
#with other pygellan functionality, this is the one that should be used
core.snap_image()
tagged_image = core.get_tagged_image()
#If using micro-manager multi-camera adapter, use core.getTaggedImage(i), where i is the camera index

#tagged_image is a tuple containing the raw pixel data (as a numpy array) and the image metadata (as a python dictionary)
pixels_flat = tagged_image[0]
metadata = tagged_image[1]
#pixels by default come out as a 1D array. We can reshape them into an image
pixels = np.reshape(pixels_flat, newshape=[metadata['Height'], metadata['Width']])
#plot it
plt.imshow(pixels,cmap='gray')
plt.show()
