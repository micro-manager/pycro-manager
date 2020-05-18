.. _acq_intro:

****************************************************************
Specifying data to acquire
****************************************************************

The :class:`Acquisition<pycromanager.Acquisition>` class enables both simple mutli-dimensional acquisitions and complex data-adaptive acquisitions. Acquisitions take instructions in the form of :ref:`acquisition events<acq_event_spec>`, which are a set of instructions for setting hardware positions for the acquisition of a single image.

.. note::

   It is essential to wrap the calling script that uses the :class:`Acquisition<pycromanager.Acquisition>` with :code:`if __name__ == '__main__':`, as shown in the examples below

Multi-dimensional acquisitions
##############################

Multi-dimensional acquisitions are a common type of acquisition in which images are collected across some set of time, z-stack, channel, and xy position. The :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` function can be used to automatically generate the required :ref:`acquisition events<acq_event_spec>`. 


The following shows a the simple example of acquiring a single z-stack:

.. code-block:: python

	from pycromanager import Acquisition, multi_d_acquisition_events

	if __name__ == '__main__': #this is important, don't forget it

		with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
		    # Generate the events for a single z-stack
		    events = multi_d_acquisition_events(z_start=0, z_end=10, z_step=0.5)
		    acq.acquire(events)

In addition to z-stacks, this function can also be used to do timelapses, different channels, and multiple XY stage positions. This example shows how to run a multi-channel timelapse with z-stacks:

.. code-block:: python

	if __name__ == '__main__':

	    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
	        events = multi_d_acquisition_events(
	    					num_time_points=4, time_interval_s=0, 
	    					channel_group='channel', channels=['DAPI', 'FITC'], 
	    					z_start=0, z_end=6, z_step=0.4, 
	    					order='tcz')


Acquisition events
####################

If more fine-grained control of the acquired data is needed, :ref:`acquisition events<acq_event_spec>` can be manually created. The following example shows the same z-stack as the example above, but with acquisition 
events created manually:

.. code-block:: python

	if __name__ == '__main__':

		with Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest') as acq:
		    #create one event for the image at each z-slice
		    events = []
		    for index, z_um in enumerate(np.arange(start=0, stop=10, step=0.5)):
		        evt = {
				#'axes' is required. It is used by the image viewer and data storage to
				#identify the acquired image
				'axes': {'z': index},
				  
				#the 'z' field provides the z position in µm
				'z': z_um}
		        events.append(evt)

		    acq.acquire(events)


This mechanism can be used to make acquisitions that vary device properties across arbitrary named axes:

.. code-block:: python

	if __name__ == '__main__':

		with Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest') as acq:
		    events = []
		    for index in range(10):
		        evt = {
				'axes': {'arbitrary_axis_name': index},
				#'properties' for the manipulation of hardware by specifying an arbitrary
				#list of properties
				'properties':
				   [['device_name', 'property_name', 'property_value'],
				    ['device_name_2', 'property_name_2', 'property_value_2']]}
		        events.append(evt)

		    acq.acquire(events)


Channels can be created by providing the group and preset name of a `Micro-manager config group <https://micro-manager.org/wiki/Micro-Manager_Configuration_Guide#Configuration_Presets>`_. The 'axes' field is not needed for channels because it is inferred automatically.

.. code-block:: python

	 event = {
	'channel': {
		'group': 'name_of_micro_manager_config_group',
		'config': 'setting_of_micro_manager_preset'
	}}

For the values in provided in the micro-manager demo config, this would be:

.. code-block:: python

	 event = {
	'channel': {
		'group': 'channel',
		'config': 'DAPI'
	}}


A description of all possible fields in an acquisition event can be found in the :ref:`acq_event_spec`

.. _magellan_acq_launch:

Micro-Magellan Acquisitions
############################
Another alternative is to launch `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ acquisitions (which generate the acquisition events automatically). This is accomplished by passing in a value to the ``magellan_acq_index`` argument, which corresponds to the position of the acquisition to be launched in the **Acquisition(s)** section of the Micro-Magellan GUI. Passing in 0 corresponds to the default acquisition. Greater numbers can be used to programatically control multiple acquisitions.


.. code-block:: python

	if __name__ == '__main__':
	
		#no need to use the normal "with" syntax because these acquisition are cleaned up automatically
		acq = Acquisition(magellan_acq_index=0)

		# Optional: block here until the acquisition is finished
		acq.await_completion()

Like the other mechanisms for running acquisitions, Micro-Magellan acquisitions can be used with :ref:`acq_hooks` and :ref:`img_processors`.

