******************************************************
Acquisitions 
******************************************************

:ref:`acq_intro` describes how ``pycromanager`` can be used for acquiring data across any number of axes (e.g. timelapses, multiple channels, Z-stacks). :ref:`acq_hooks` can be used to modify acquisition control on-the-fly or synchrnoize hardware outside of micro-manager with acquisition. :ref:`img_processors` can be used to modify images during before saving/display or to divert images away from display/saving to custom endpoints. :ref:`reading_data` describes how to read the acquired data  as ``numpy`` or ``dask`` arrays for processing or visualization.


###############################

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_intro
	acq_hooks
	img_processors
	read_data
	magellan_api

