==============
API Reference
==============

.. _acq_event_spec:

Acquisition event specification
###############################

The following shows all possible fields in an acquisition event (not all of which are required). An acquisition event which does not contain either the `'channel'` key or the `'axes'` key will not acquire an image, and can be used to control hardware only. 

.. code-block:: python

  event = {
	#A dictionary with the positions along various axes (e.g. time point indez,
	#z-slice index, etc) a 'channel' axis is not required as it is inferred 
	#automatically
	'axes': {'axis1_name': integer_value,
			 'axis2_name': integer_value},

	#The config of group and setting corresponding to this channel
	'channel': {
		'group': 'name_of_micro_manager_config_group',
		'config': 'setting_of_micro_manager_config_group'
	},

	'exposure': exposure_time_in_ms,

	#For z stacks
	'z': z_position_in_µm,

	#For timelapses: how long to wait before starting next time point in s
	'min_start_time': time_in_s

	#For XY stages
	'x': x_position_in_µm,
	'y': y_position_in_µm,
	#If xy stage positions are in a grid
	'row': row_index_of_xy_position,
	'col': col_index_of_xy_position,

	#Turn of autoshutter, and keep the shutter open while acquiring
	'keep_shutter_open': True,

	#Other arbitrary hardware settings can be encoded in a list of strings with
	#each entry containing the name of the device, the name of the property,
	#and the value of the property
	'properties': [['DeviceName', 'PropertyName', 'PropertyValue'], 
		['OtherDeviceName', 'OtherPropertyName', 'OtherPropertyValue']],
	}
    


Acquisition APIs
#######################################################

Acquisition
==============
.. currentmodule:: pycromanager
.. autoclass:: Acquisition
	:members:

multi_d_acquisition_events
===========================
.. autofunction:: multi_d_acquisition_events

XYTiledAcquisition
=====================
.. autoclass:: XYTiledAcquisition
	:members:

MagellanAcquisition
=======================
.. autoclass:: MagellanAcquisition
	:members:

start_headless
===========================
.. autofunction:: start_headless


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
