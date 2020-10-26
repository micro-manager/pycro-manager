import numpy as np
from pycromanager import Dataset
import napari

# This path is to the top level of the magellan dataset (i.e. the one that contains the Full resolution folder)
# data_path = '/Users/henrypinkard/megllandump/l_axis_1'
# data_path = '/Users/henrypinkard/megllandump/l_axis_3'
data_path = "/Users/henrypinkard/megllandump/experiment_1_11"

# open the dataset
dataset = Dataset(data_path)

# read tiles or tiles + metadata by channel, slice, time, and position indices
# img is a numpy array and md is a python dictionary
img, img_metadata = dataset.read_image(l=10, read_metadata=True)

dask_array = dataset.as_array(stitched=True)

with napari.gui_qt():
    v = napari.Viewer()
    v.add_image(dask_array)
