from pygellan.acquire import MagellanBridge
import numpy as np
import matplotlib.pyplot as plt

#### Setup ####
#establish communication with Magellan
bridge = MagellanBridge()
magellan = bridge.get_magellan()

#create 3x3 grid centered at 0.0 stage coordinates
magellan.create_grid('New_grid', 3, 3, 0.0, 0.0)

#TODO: add delete grids and surface funcitons to API