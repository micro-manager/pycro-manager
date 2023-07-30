******************************************************
Acquisitions 
******************************************************

The :class:`Acquisition<pycromanager.Acquisition>` class is a flexible abstraction built to support a multitude of microscopy experiments. It's essential functions are to parse a set of instructions from the user known as "acquisition events", control the microscope hardware according to these, and efficiently retrieve, save, and provide access to image data from the camera(s). Each of these functionalities can be further modified and/or customized in a variety of ways.

The following shows a minimal example of using :class:`Acquisition<pycromanager.Acquisition>` class to acquire a sequence of 5 images from the camera and save them to disk:

.. code-block:: python

	from pycromanager import Acquisition, multi_d_acquisition_events

	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
	    events = multi_d_acquisition_events(num_time_points=5)
	    acq.acquire(events)


The data will be displayed in the default :ref:`image viewer <viewers>` as it is acquired, and it can be also be accessed through the :class:`Dataset<pycromanager.Dataset>` class:

.. code-block:: python

	dataset = acq.get_dataset()
	img = dataset.read_image(time=0) # a numpy array



Standard Multi-Dimensional Acquisitions
=========================================

In Micro-Manager/Pycro-Manager, "multi-dimensional acquisitions" refer to experiments where images are systematically collected across various combinations of time, z-stack, channel, and xy position axes. Pycro-Manager provides the :meth:`multi_d_acquisition_events<pycromanager.multi_d_acquisition_events>` function for generating the instructions (acquisition events) to acquire this type of data.

The following shows an example of acquiring a single z-stack:

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
    	acq.acquire(events)

More information on this function can be found in the `MDA Tutorial <application_notebooks/multi-d-acq-tutorial.ipynb>`_



Special types of Acquisitions
================================


In addition to the regular :class:`Acquisition<pycromanager.Acquisition>` class, Pycro-manager provides a few :ref:`special types of Acquisitions <special_acqs>`, with features designed for specific applications. 

 - :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>` can be used to image samples that are larger than a single field of view by moving around an XY stage and capturing multiple images, then stitching them together into a single contiguous image. It uses a special, multi-resolution file format to facilitate efficient visualization of the data at multiple scales
 - An :class:`ExploreAcquisition<pycromanager.ExploreAcquisition>` is a special type of :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>` that provides a user interface for moving around a XY and Z stage and telling the microscope where to Image
 - The :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>` is a special type of :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>` for controlling the `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ plugin. This plugin provides additional features for mapping samples, defining parts of the sample to image, and collecting specialized 3D datasets.




Hardware sequencing
=====================
An important function of the acquisition engine underlying Pycro-Manager is to enable hardware sequencing. In hardware sequencing, multiple images are captured without the computer and hardware having to communicate between each one. In certain cases, this can dramatically increase the speed with which data is acquired. For high-performance applications, hardware sequencing is essential to speed and sufficiently precise synchronization between different hardware components.

The :doc:`application_notebooks/external_hardware_triggering_tutorial` tutorial shows an example of this in action.

Pycro-manager acquisitions will automatically try to use hardware sequencing when the following conditions are met:
 
 1. there are no delays requested between successive image
 2. Any hardware that changes positions between successive images also supports being sent a sequence of instructions that it can execute at once
 3. The events to be sequenced over were all submitted to ``acq.acquire()`` in a single call.

If an acquisition hook is being used and hardware sequencing is engaged, the ``event`` that gets passed to the hook will not being a single python ``dict``, but instead a ``list`` of ``dict`` objects representing a sequence of events. It will also only be called once, for the whole sequence, instead of once for each event.

If desired, hardware sequencing can be turned off by submitting events for acquisition one at a time. For a list of acquisition events called ``events``:


.. code-block:: python

	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
		# Create a list of events
		events = multi_d_acquisition_events(num_time_points=10)
		# but submit them one at a time so sequencing doesn't occur
		for event in events:
			acq.acquire(event)





Customizing Acquisitions
============================

While executing the :class:`Acquisition<pycromanager.Acquisition>` code, several operations are taking place concurrently: events are being interpreted and queued for execution, hardware is being controlled and monitored, and images are being retrieved and saved. To ensure efficient execution, these operations are performed in parallel wherever feasible. 

To tailor an :class:`Acquisition<pycromanager.Acquisition>` to your needs, you may need to interact with specific parts of this process. For this, Pycro-manager provides dedicated APIs, each designed to enable customization for a specific piece of the acquisition process: 

 - Creating :ref:`acq_events` tells the :class:`Acquisition<pycromanager.Acquisition>` what to acquire and how to acquire it. 
 - :ref:`acq_hooks` allow alterations to the standard progression of hardware control through injecting custom user code.
 - :ref:`img_processors` allow modification/processing of image data prior to saving/displaying, or for images to be rerouted to custom endpoints instead of being saved to disk.


The figure below shows an overview of what happens behind the scenes during an acquisition and where the each API fits. Each color represents a distinct thread that is operating asynchronously from the others.


.. figure:: acquisition_figure.png
   :width: 800
   :alt: Overview figure of pycro-manager Acquisitions

   **Pycro-Manager's high-level programming interface.** The data acquisition process in Pycro-Manager starts with (blue) a source of acquisition events, which can come from code or a graphical user interface. These events are passed to (green) the hardware control thread, which optimizes them to take advantage of hardware triggering where available, sends instructions to hardware, and acquires images. (Magenta) The resulting images are then saved and displayed in the GUI. The three main abstractions of the Pycro-Manager high-level programming interface (acquisition events, acquisition hooks, and image processors) enable fine-grained control and customization of this process.

###############################

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_events
	acq_hooks
	img_processors
	image_saved_callbacks
	viewers
	special_acqs
	






