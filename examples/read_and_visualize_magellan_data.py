import numpy as np
from pygellan.magellan_data import MagellanDataset
import napari

#This path is to the top level of the magellan dataset (i.e. the one that contains the Full resolution folder)
data_path = '/path/to/data'

#open the dataset
magellan = MagellanDataset(data_path)

#read tiles or tiles + metadata by channel, slice, time, and position indices
#img is a numpy array and md is a python dictionary
img, img_metadata = magellan.read_image(channel_index=0, z_index=30, pos_index=20, read_metadata=True)

#Alternatively, all data can be opened at once in a single dask array. Using dask arrays enables all_data to be
#held in a single memory-mapped array (i.e. the data are not loaded in RAM until they are used, enabing a convenient
#way to work with data larger than the computer's memory. Dask arrays also enable visulization in Napari (see below),
#and allow for code to be prototyped on a small computers and scaled up to clusters without having to rewrite code.
#More information can be found at https://dask.org/
all_data = magellan.as_array(stitched=True) #returns an array with 5 dimensions corresponding to time-channel-z-y-x
# all_data = magellan.as_array(stitched=False) #this version has a leading axis for position

#dask array can be used just like numpy array
#take max intenisty z projection of z stack at time point 0 in channel 0
max_intensity = np.max(all_data[0, 0], axis=0)

#visualize data using napari--this example will likely updated as the napari API changes and improves
with napari.gui_qt():
    napari.view(all_data, clim_range=[0, 255])