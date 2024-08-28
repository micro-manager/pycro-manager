.. _acq_events:

****************************************************************
Custom Acquisition Events
****************************************************************

Acquisition events in Pycro-Manager are Python dictionaries that define how hardware is controlled and images are acquired. While the ``multi_d_acquisition_events()`` function can generate events for common scenarios, custom events offer greater flexibility and control for more complex imaging protocols.

A full description of all possible fields in an acquisition event can be found in the :ref:`acq_event_spec`.


Basic Structure
---------------

Every event must have an ``axes`` field to uniquely identify the resulting image:

.. code-block:: python

    event = {
        'axes': {'time': 0, 'z': 3, 'channel': 'DAPI'}
    }

The position in each axis can be either an int or a string.

In most cases, each event will produce a single image. Thus, a series of images in a time-lapse acquisition might be defined as:

.. code-block:: python

    event_0 = { 'axes': {'time': 0} }
    event_1 = { 'axes': {'time': 1} }
    event_2 = { 'axes': {'time': 2} }


In addition to the ``axes`` field, events other fields that determine how the hardware is controlled (see :ref:`acq_event_spec` for a complete listing of these).

For example, the ``'z'`` field specifies the z position of the focus stage in microns. A Z-stack acquisition can be performed by creating events with different z positions:

.. code-block:: python

    with Acquisition('/path/to/data', 'z_stack_acq') as acq:
        events = []
        for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
            evt = {
                'axes': {'z': index},  # this indexes the resulting image
                'z': z_um  # this specifies the z position in microns
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
                # 'properties' allows manipulation of hardware by specifying an arbitrary
                # list of properties
                'properties': [
                    ['device_name', 'property_name', 'property_value'],
                    ['device_name_2', 'property_name_2', 'property_value_2']
                ]
            }
            events.append(evt)
        acq.acquire(events)


For a practical example of custom events in action, see the `Intermittent Z-T Acquisition tutorial <intermittent_Z_T.ipynb>`_, which demonstrates how to acquire alternating time series and z-stacks.


.. toctree::
   :maxdepth: 1
   :hidden:

   intermittent_Z_T.ipynb

The channel axis
==========================
The ``channel`` axis has unique behavior: it not only determines the storage of images like other axes but also their display in the default viewer (:ref:`viewers`). Images with different ``channel`` values but matching other axes are overlaid in the default viewer.

In Micro-Manager, hardware settings for different channels are typically controlled by providing the group and preset name of a `Config group <https://micro-manager.org/wiki/Micro-Manager_Configuration_Guide#Configuration_Presets>`_. This is specified using the ``config_group`` field of acquisition events. These hardware control instructions can be specified independently of how the image is stored/displayed in the acquisition event.


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

