.. _reading_data:

******************************************************
Reading acquired data
******************************************************

The `NDTiff format <https://github.com/micro-manager/NDTiffStorage>`_ is the default saving format of ``pycromanager`` :class:`Acquisition<pycromanager.Acquisition>`s, as well as acquisitions run using Micro-Magellan. Data saved in this format can be read either during or after an acquisition. In either case, access to the underlying data is provided by a :class:`Dataset<pycromanager.Dataset>` object.  

Images can be loaded individually, or all data can be loaded simulataneously into a memory-mapped `dask <https://dask.org/>`_ array. This is a "virtual" array, which means the whole dataset isn't loaded into RAM at first, but is instead "lazily" brought into RAM as each sub-part of it is used. This allows for processing of large datasets and viewing data in `napari <https://github.com/napari/napari>`_. 

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

	img = dataset.read_image(z=0)
	img_metadata dataset.read_metadata(z=0)

	#img is a numpy array, img_metadata is a dict

To determine which axes are available, access the ``Dataset.axes`` attribute, which contains a dict with axis names as keys and a list of available indices as values.

If the dataset was created by tiling multiple XY positions, tiles along the axis corresponding to XY positions can be indexed by their row and column positions: 

.. code-block:: python

	img = dataset.read_image(row=0, col=1)


Opening data as Dask array
##############################

Rather than reading each image individually, all data can be opened at once in a single dask array. Using dask arrays enables all_data to be held in a single memory-mapped array. This means that the data are not loaded in RAM until they are used, enabing a convenient way to work with datasets larger than the computer's RAM. Dask arrays also enable `https://napari.org/tutorials/applications/dask <visulization in napari>`_ and allow for code to be prototyped on a small computers and scaled up to clusters without having to rewrite code.

.. code-block:: python

	dask_array = dataset.as_array() 

	#dask array can be used just like numpy array
	#take max intenisty projection along axis 0
	max_intensity = np.max(all_data[0, 0], axis=0)

	#visualize data using napari
	v = napari.Viewer()
	v.add_image(dask_array)
	napari.run()


If the data was acquired by an :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>` or a :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>` the grid on XY images can be automatically stitched into one contiguous image:

.. code-block:: python

	dask_array = dataset.as_array(stitched=True) 


You can also slice along particular axes when creating the dask array:

.. code-block:: python

	dask_array = dataset.as_array(z=0, time=2) 


