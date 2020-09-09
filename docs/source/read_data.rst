.. _reading_data:

******************************************************
Reading saved data
******************************************************

This section describes how to read image data and metadata from multidimensional datasets saved in the default `NDTiff format <https://github.com/micro-manager/NDTiffStorage>`_ of ``pycromanager``. This can take place either during or after an acquisition. In either case, access to the underlying data is provided by a :class:`Dataset<pycromanager.Dataset>` object.  

Images can be loaded individually, or all data can be loaded simulataneously into a memory-mapped `dask <https://dask.org/>`_ array, which works like a numpy array and also allows scalable processing of large datasets and viewing data in `napari <https://github.com/napari/napari>`_. 

Creating a ``Dataset`` object
##############################

There are two ways to do this, depending on whether the data is part of an in-progress acquisition or not. In the former case:

.. code-block:: python

	from pycromanager import Acquisition

    with Acquisition('/path/to/saving/dir', 'saving_name') as acq:

    	### send some instructions so something is acquired ######

        dataset = acq.get_dataset()

Alternatively, to open a finished dataset from disk:


.. code-block:: python

	from pycromanager import Dataset

	#This path is to the top level of the dataset 
	data_path = '/path/to/data'

	dataset = Dataset(data_path)


Reading data
##############################

Once opened, individual tiles can be accessed using :meth:`read_image<pycromanager.Dataset.read_image>`. This method accepts positions along different dimensions as argument. For example, to get the first image in a z stack, pass in `z=0` as an argument.

.. code-block:: python

	img, img_metadata = dataset.read_image(z=0, read_metadata=True)

	#img is a numpy array, img_metadata is a dict

To determine which axes are available, access the ``Dataset.axes`` attribute, which contains a dict with axis names as keys and a list of available indices as values.

If the dataset was created by tiling multiple XY positions, tiles along the axis corresponding to XY positions can be indexed 
by their row and column positions: 

.. code-block:: python

	img = dataset.read_image(row=0, col=1)


Opening data as Dask array
##############################

Rather than reading each image individually, all data can be opened at once in a single dask array. Using dask arrays enables all_data to be held in a single memory-mapped array (i.e. the data are not loaded in RAM until they are used, enabing a convenient way to work with data larger than the computer's memory. Dask arrays also enable `https://napari.org/tutorials/applications/dask <visulization in napari>`_ and allow for code to be prototyped on a small computers and scaled up to clusters without having to rewrite code.

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



