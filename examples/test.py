import numpy as np
from pygellan.magellan_data import MagellanDataset
import napari

#This path is to the top level of the magellan dataset (i.e. the one that contains the Full resolution folder)
data_path = '/Users/henrypinkard/megllandump/Untitled_142'

#open the dataset
magellan = MagellanDataset(data_path)

