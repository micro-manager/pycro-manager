.. _acq_events:

****************************************************************
Types of Acquisitions
****************************************************************

The :class:`Acquisition<pycromanager.Acquisition>` class enables specification of common microscopy workflows (like timelapses, z-stacks, etc.) as well as a great deal of customization for more complex applications like data-adaptive acquisitions. 

There are subclasses of :class:`Acquisition<pycromanager.Acquisition>` that allow for special types of acquisitions, like :ref:`xy_tiled_acq`, which can be used to stich together multiple fields of view using an XY stage and :ref:`magellan_acq_launch`, which provides an interactive GUI for navigating around a large sample.

Acquisition
========================

The generic :class:`Acquisition<pycromanager.Acquisition>` is extremely flexible and can be used to implement many types of microscopy workflows.

:class:`Acquisition<pycromanager.Acquisition>` take instructions in the form of :ref:`acquisition events<acq_event_spec>`, each of which is a set of instructions for the hardware settings corresponding to a single image.

The general syntax for using an :class:`Acquisition<pycromanager.Acquisition>` is:

.. code-block:: python

	from pycromanager import Acquisition

	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
	    
	    # Create some acquisition events here:
	    # events = 
	    
	    acq.acquire(events)


An acquisition event is a Python ``dict`` object with a specific structure. Most importantly, it has an ``axes`` field that contains a unique identifier for the image that will be generated, formed by supplying an integer index for each of the dimensions over which images in the acquisition will vary. For example, in a timelapse of ten images would vary only over the ``time`` axis, and the first two events would be: 

.. code-block:: python

	event_0 = { 'axes': {'time': 0} }
	event_1 = { 'axes': {'time': 1} }

Acquisition events often also contain information about how to move hardware before acquiring an image (for example, an XY position for a stage), which will be described more below.

You can create :ref:`manual_acq_events` from scratch, but in many cases it is easier to use the :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` convenience function for generating events.

multi_d_acquisition_events
____________________________

"Multi-dimensional acquisition" refers to a common type of acquisition in which images are collected across some set of time, z-stack, channel, and xy position axes. If additional axes beyond these 4 are needed, you'll need to manually create :ref:`manual_acq_events`. The :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` function can be used to automatically generate the required :ref:`acquisition events<acq_event_spec>`. 


The following shows a the simple example of acquiring a single z-stack:

.. code-block:: python

	from pycromanager import Acquisition, multi_d_acquisition_events

	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
	    # Generate the events for a single z-stack
	    events = multi_d_acquisition_events(z_start=0, z_end=10, z_step=0.5)
	    acq.acquire(events)

In addition to z-stacks, this function can also be used to do timelapses, different channels, and multiple XY stage positions. This example shows how to run a multi-channel timelapse with z-stacks:

.. code-block:: python

    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
        events = multi_d_acquisition_events(
    					num_time_points=4, time_interval_s=0, 
    					channel_group='Channel', channels=['DAPI', 'FITC'], 
    					z_start=0, z_end=6, z_step=0.4, 
    					order='tcz')

More information on this function can be found in the `MDA Tutorial <application_notebooks/multi-d-acq-tutorial.ipynb>`_


.. _manual_acq_events:

Customized acquisition events
_______________________________

If more fine-grained control of the acquired data is needed, acquisition events can be built from scratch. A full description of all possible fields in an acquisition event can be found in the :ref:`acq_event_spec`. 

The following example shows the same z-stack as the example above, but with acquisition events created from scratch:

.. code-block:: python

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
		'group': 'Channel',
		'config': 'DAPI'
	}}


.. _xy_tiled_acq:

XYTiled Acquisition
========================
Pycro-manager has special support for acquisitions in which multiple images are tiled together to form large, high-resolution images. In this mode, data will automatically be saved in a multi-resolution pyramid, so that it can be efficiently viewed at multiple levels of zoom. These features are also available though `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_, which provides an interactive GUI as well as other higher level features.


.. note::

   In order for this functionality to work, the current configuration must have a correctly calibrated affine transform matrix, which gives the corrspondence between the coordinate systems of the camera and the XY stage. This can be calibrated automatically in Micro-Manager by using the pixel size calibrator (under ``Devices``--``Pixel Size Calibration`` in the Micro-manager GUI).

To use these features, rather than creating an :class:`Acquisition<pycromanager.Acquisition>`, a :class:`XYTiledAcquisition<pycromanager.Acquisition>` will be used. These classes are almost identical, except that :class:`XYTiledAcquisition<pycromanager.Acquisition>` has an additional required argument ``tile_overlap``, which gives the number of pixels by which adjacent tiles will overlap. Different XY fields of view can be acquired using the ``row`` and ``col`` fields in acquisition events.


.. code-block:: python

    from pycromanager import XYTiledAcquisition

    with XYTiledAcquisition(directory='/path/to/saving/dir', name='saving_name', tile_overlap=10) as acq:
        #10 pixel overlap between adjacent tiles

        #acquire a 2 x 1 grid
        acq.acquire({'row': 0, 'col': 0})
        acq.acquire({'row': 1, 'col': 0})



.. _magellan_acq_launch:

Micro-Magellan Acquisition
===============================
Another alternative is to launch `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ acquisitions. These include both regular and `explore acquisitions <https://micro-manager.org/wiki/MicroMagellan#Explore_Acquisitions>`_, which launches an interactive GUI for navigating around a sample in XY and Z and clicking to collect images. 

Micro-Magellan acquisitions can be run using the :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>` class. The class requires as an argument either ``magellan_acq_index`` or ``magellan_explore``. The former corresponds to the position of the acquisition to be launched in the **Acquisition(s)** section of the Micro-Magellan GUI. Passing in 0 corresponds to the default acquisition. Greater numbers can be used to programatically control multiple acquisitions. The latter corresponds to explore acquisitions, which can be launched by setting the ``magellan_explore`` argument equal to ``True``.


.. code-block:: python

	from pycromanager import MagellanAcquisition

	# no need to use the normal "with" syntax because these acquisition are cleaned up automatically
	acq = MagellanAcquisition(magellan_acq_index=0)

	# Or do this to launch an explore acquisition
	acq = MagellanAcquisition(magellan_explore=True)

	# Optional: block here until the acquisition is finished
	acq.await_completion()

Like the other mechanisms for running acquisitions, Micro-Magellan acquisitions can be used with :ref:`acq_hooks` and :ref:`img_processors`.

