******************************************************
Acquisitions 
******************************************************

The :class:`Acquisition<pycromanager.Acquisition>` class is a powerful abstraction that can be used for a wide range of microscopy workflows. The only requirement for running an acquisition is to use one of several possible mechanisms for :ref:`acq_events`

More advanced functionality can be implemented through the use of :ref:`acq_hooks`, which are used to modify acquisition control on-the-fly or synchrnoize hardware outside of micro-manager with acquisition, or with :ref:`img_processors`, which can be used to modify images during before saving/display or to divert images away from display/saving to custom endpoints.

The :class:`Acquisition<pycromanager.Acquisition>`'s class can also be used for :ref:`hardware_triggering`.

:ref:`reading_data` describes how to read the data acquired by an :class:`Acquisition<pycromanager.Acquisition>` as ``numpy`` or ``dask`` array.

The figure figure below gives an overview of all of the features this class provides.

.. figure:: acquisition_figure.png
   :width: 800
   :alt: Overview figure of pycro-manager Acquisitions

   Overview of pycro-manager Acquisitions. The blue boxes show acquisitions starting with some source of ”acquisition events”, instructions for image collection and associated hardware changes. Green boxes represent acquisition events that are optimized, then used to move hardware and collect images. ”Acquisition hooks” can be used to execute arbitrary code synchronously or modify/delete instructions on-the-fly. Magenta boxes represent acquired images going straight to the default image saving and display, or being diverted through ”image processors”, which allow for modification of images or diversion to external saving and visualization.







###############################

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_events
	acq_hooks
	img_processors
	hardware_triggering


