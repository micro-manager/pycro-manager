.. _acq_events:

****************************************************************
Custom Acquisition Events
****************************************************************

An acquisition event is a Python ``dict`` object with a specific structure. The :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` function can be used to create these events, but since it only covers a limited number of use cases, it often may be more useful to create them manually.


Every event must have an ``axes`` field that uniquely identifies the image that the event will produce. This field is a  dictionary which contains the name and position of each axis used to identify the image. The position can either be an int or a string.

For example, in a timelapse of ten images would vary only over the ``time`` axis, and the first two events would be: 

.. code-block:: python

	event_0 = { 'axes': {'time': 0} }
	event_1 = { 'axes': {'time': 1} }

A full description of all possible fields in an acquisition event can be found in the :ref:`acq_event_spec`. 

The following example shows the a the events used to acquire a z-stack. Note that this is primarily for demonstration purposes, as the same events can be generated more conveniently using the :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` function.


.. code-block:: python

	with Acquisition('/path/to/data', 'acq_name') as acq:
	    # create one event for the image at each z-slice
	    events = []
	    for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
	        evt = {
			# 'axes' is required. It is used by the image viewer and data storage to
			# identify the acquired image
			'axes': {'z': index},
			  
			# the 'z' field provides the z position in µm
			'z': z_um
			}
	        events.append(evt)

	    acq.acquire(events)



Creating custom acquisition events provides more flexibility in controlling hardware. For example, custom device properties can be specified in events:

.. code-block:: python

	with Acquisition('/path/to/data', 'acq_name') as acq:
	    events = []
	    for index in range(10):
	        evt = {
			'axes': {'arbitrary_axis_name': index},
			#'properties' for the manipulation of hardware by specifying an arbitrary
			#list of properties
			'properties':
			   [['device_name', 'property_name', 'property_value'],
			    ['device_name_2', 'property_name_2', 'property_value_2']]
			  }
	        events.append(evt)

	    acq.acquire(events)



The channel axis
==========================
The axis ``"channel"`` has a special significance because it not only determines how the corresponding image is stored, it also determines how it is displayed in the default viewer. Images with different ``"channel"`` values that match on all the other axes will by default be overlayed in a multi-channel image.

In Micro-Manager, hardware settings for different channels are typically controlled by providing the group and preset name of a `Config group <https://micro-manager.org/wiki/Micro-Manager_Configuration_Guide#Configuration_Presets>`_. This is specified using the ``config_group`` field of acquisition events. These hardware control instructions can be specified independently of how the image is stored/displayed in the acquisition event

.. code-block:: python

	 event = {
		'axes': {'channel': 'desired_name_for_saving_and_display'},
		'config_group': 
			['name_of_micro_manager_config_group',
			'setting_of_micro_manager_preset']
	}

For example, with the values in provided in the micro-manager demo config, this would be:

.. code-block:: python

	 event = {
		'axes': {'channel': 'DAPI'},
		'config_group': ['Channel', 'DAPI']
	}


Specifying these separately allows images multiple or different hardware properties to be overlayed as channels in the display.

