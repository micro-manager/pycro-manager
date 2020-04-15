.. _reading_data:

******************************************************
Opening acquired data
******************************************************

This section describes how to read image data nd metadata from multidimensional datasets saved in the default NDTiff format of ``pycromanager``. Tiles can be loaded individually, or all data can be loaded simulataneously into a memory-mapped `dask <https://dask.org/>`_ array, which works like a numpy array and also allows scalable processing of large datasets and viewing data in `napari <https://github.com/napari/napari>`_. 

To open a dataset:

.. code-block:: python

	from pycromanager import Dataset

	#This path is to the top level of the dataset 
	data_path = '/path/to/data'

	#open the dataset
	dataset = Dataset(data_path)

Once opened, individual tiles can be accessed using :meth:`read_image<pycromanager.Dataset.read_image>`. This method accepts positions along different dimensions as argument. For example, to get the first image in a z stack, pass in `z=0` as an argument.

.. code-block:: python

	img, img_metadata = dataset.read_image(z=0, read_metadata=True)

	#img is a numpy array, img_metadata is a dict

To determine which axes are available, access the ``Dataset.axes`` attribute, which contains a dict with axis names as keys and a list of available indices as values.


Alternatively, all data can be opened at once in a single dask array. Using dask arrays enables all_data to be held in a single memory-mapped array (i.e. the data are not loaded in RAM until they are used, enabing a convenient way to work with data larger than the computer's memory. Dask arrays also enable `https://napari.org/tutorials/applications/dask <visulization in napari>`_ and allow for code to be prototyped on a small computers and scaled up to clusters without having to rewrite code.

.. code-block:: python

	dask_array = dataset.as_array() 

	#dask array can be used just like numpy array
	#take max intenisty projection along axis 0
	max_intensity = np.max(all_data[0, 0], axis=0)

	#visualize data using napari
	with napari.gui_qt():
	    v = napari.Viewer()
	    v.add_image(dask_array)


If the data was acquired in an XY grid of position (such as Micro-Magellan datasets are), the array can be automatically stitched:

.. code-block:: python

	dask_array = dataset.as_array(stitched=True) 

	with napari.gui_qt():
	    v = napari.Viewer()
	    v.add_image(dask_array)



