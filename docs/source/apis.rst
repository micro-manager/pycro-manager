==============
API Reference
==============

.. _acq_event_spec:

Acquisition event specification
###############################

The following shows all possible fields in an acquisition event (not all of which are required). An acquisition event which does not contain either the `'channel'` key or the `'axes'` key will not acquire an image, and can be used to control hardware only. 

.. code-block:: python

  event = {
	# A dictionary with the positions along various axes (e.g. time point index,
	# z-slice index, etc.). 
	'axes': {
		# Axis names can be any string
		'axis1_name': 1,

		# They can take integer or string values
		'axis2_name': 'first_position', 

		# "channel" is a special axis name which will lead to different positions being 
		# overlayed in different colors in the image viewer
		'channel': 'DAPI',

		# If an XYTiledAcquisition is being used, "row" and "column" are special 
		# values that the acquisition engine will convert into stage coordinates,
		# laying out the acquired images in a grid
		'row': 1,
		'column': 0,

		},

	# Config groups can be used to control groups of properties
	'config_group': ['name_of_config_group', 'name_of_preset'],

	'exposure': 10.6, # exposure time in ms

	# Z stages
	# The 'z' field controls the default z stage device (i.e. the Core-Focus device)
	'z': 123.45, # the z position in um

	# Alternatively the device can be specified by name, or multiple devices can 
	# be controlled by providing their names and positions in um
	'stage_positions': 
			[['z_stage1_name': 12.34], 
			['z_stage2_name': 1234.566]],


	# For timelapses: how long to wait before starting next time point in s
	'min_start_time': 100

	# For XY stages
	'x': 123.4, # positions in um
	'y': 567.8,



	# If using a camera other than the 'Core-camera', it can be specified by name here
	'camera': 'a_camera_device_name',


	# Other arbitrary hardware settings can be encoded in a list of strings with
	# each entry containing the name of the device, the name of the property,
	# and the value of the property
	'properties': [['DeviceName', 'PropertyName', 'PropertyValue'], 
		['OtherDeviceName', 'OtherPropertyName', 'OtherPropertyValue']],


	# Custom metadata can be added to the event, which will be added to the metadata 
	# of the resultant image under the 'tags' key
	'tags': {
		'whatever_you_want_here': 54,
		'something_else': 'here'}


	}
    


Acquisition APIs
#######################################################

Acquisition
==============
.. currentmodule:: pycromanager.acquisition.acquisition_superclass
.. autoclass:: Acquisition
	:members:


.. currentmodule:: pycromanager

multi_d_acquisition_events
===========================
.. autofunction:: multi_d_acquisition_events

XYTiledAcquisition
=====================
.. autoclass:: XYTiledAcquisition
	:members:

ExploreAcquisition
=====================
.. autoclass:: ExploreAcquisition
	:members:

MagellanAcquisition
=======================
.. autoclass:: MagellanAcquisition
	:members:


Headless mode
#######################################################

start_headless
===========================
.. autofunction:: start_headless

stop_headless
===========================
.. autofunction:: stop_headless


Dataset
##############################################

.. currentmodule:: pycromanager
.. autoclass:: Dataset
	:members:

.. currentmodule:: ndtiff
.. autoclass:: NDTiffDataset
	:members:
.. autoclass:: NDTiffPyramidDataset
	:members:

Micro-Manager Core
###################################

The core API is discovered dynamically at runtime, though not every method is implemented. Typing ``core.`` and using autocomplete with ``IPython`` is the best way to discover which functions are available. Documentation on for the Java version of the core API (which ``pycromanager`` calls) can be found `here <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html>`_.

.. currentmodule:: pycromanager
.. autoclass:: Core
	:members:


Java objects and classes
###################################

.. autoclass:: JavaObject
	:members:

.. autoclass:: JavaClass
	:members:


Convenience classes for special Java objects
===============================================

.. autoclass:: Magellan
	:members:

.. autoclass:: Studio
	:members:
