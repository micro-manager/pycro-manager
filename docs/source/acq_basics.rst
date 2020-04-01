******************************************************
The ``Acquisition`` class
******************************************************

This class is a powerful abstraction which enables both simple mutli-dimensional acquisitions and complex data-adaptive acquisitions.



####################
show how to do regular MDA


stuff
##############
.. code-block:: python

	from pycromanager.acquire import Acquisition

	acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name')
	acq.acquire(first)



Acquisition events
####################
Acquisition hooks enable the execution of arbitrary code at different points in the acquisition cycle. 


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

	#For XY stages
	'x': x_position_in_µm,
	'y': y_position_in_µm,
	#Optional if xy stage positions are in a grid
	'row': row_index_of_xy_position,
	'col': col_index_of_xy_position,

	#Other arbitrary hardware settings can be encoded in a list of strings with
	#each entry containing the name of the device, the name of the property,
	#and the value of the property seperated with '-'
	'properties': ['DeviceName-PropertyName-PropertyValue', 
				   'OtherDeviceName-OtherPropertyName-OtherPropertyValue'],
	}
    



Acq hooks
####################
Acquisition hooks enable modification of acquisition events on-the-fly, or the execution of arbitarary code at different points in the acquisition cycle. Hooks can either be executed just before the hardware updates for a particular acquisition event, or just after the hardware updates (just before the image(s) is captured. Hooks are passed into the constructor of an Acquisition. The simplest type of acquisition hook is function that takes a single
argument (the current acquisition event)

The simplest form of an acquisition hook is:

.. code-block:: python

  def hook_fn(event):
	### Do some other stuff here ###
	return event

  acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
    		post_hardware_hook_fn=hook_fn)

This form might be used, for example, to control other hardware and have it synchronized with acquisition

Acquisition hooks can also be used to modify or delete acquisition events:

.. code-block:: python

  def hook_fn(event):
	if some_condition:
		return event
	# if condition isn't met, delete this event by not returning it





image processors
####################