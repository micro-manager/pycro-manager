******************************************************
Acquisitions 
******************************************************

The :class:`Acquisition<pycromanager.Acquisition>` class is a powerful abstraction that can be used for a wide range of microscopy workflows. The figure figure below gives an overview of some of the features this class provides.

.. figure:: acquisition_figure.png
   :width: 800
   :alt: Overview figure of pycro-manager Acquisitions

   **Pycro-Manager's high-level programming interface.** The data acquisition process in Pycro-Manager starts with (blue) a source of acquisition events (from either a programming or GUI). These events are passed to (green) the acquisition engine, which optimizes them to take advantage of hardware triggering where available, sends instructions to hardware, and acquires images. (Magenta) The resulting images are then saved and displayed in the GUI. The three main abstractions of the Pycro-Manager high-level programming interface (acquisition events, acquisition hooks, and image processors) enable fine-grained control and customization of this process.

An :class:`Acquisition<pycromanager.Acquisition>` can be run alongside the Micro-Manager GUI, or can be launched without it in :ref:`headless_mode`. ``pycromanager`` provides different options for :ref:`viewers` of acquired data. By turning off the default image viewer, the :class:`Acquisition<pycromanager.Acquisition>` class can be used as a data acquisition backend for custom applications.

Several different :ref:`acq_events` are possible within the :class:`Acquisition<pycromanager.Acquisition>` class.

More advanced functionality can be implemented through the use of :ref:`acq_hooks`. They can be used to modify the acquisition on-the-fly or to control hardware with python API outside of micro-manager. :ref:`img_processors` can further be used to modify images during before saving/display or to divert images towards custom endpoints.

The :ref:`performance_guide` describes best coding practices for maximizing the throughput of :class:`Acquisition<pycromanager.Acquisition>` and how to use ``pycromanager`` with microscopes that use :ref:`hardware_triggering`.

:ref:`reading_data` describes how to read the data acquired as a ``numpy`` or ``dask`` array.

###############################

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_events
	acq_hooks
	img_processors
	image_saved_callbacks
	viewers
	headless_mode
	performance_guide
	