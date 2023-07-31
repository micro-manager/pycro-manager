****************
User Guide
****************

After completing the :ref:`setup`, there are two options for running Pycro-Manager: It can be run alongside the Micro-Manager application by launching Micro-Manager the desktop in the typical way, or it can be run in :ref:`headless_mode`. In this mode, an invisible backend is launched as a separate process, and the Micro-Manager GUI does not appear.

Pycro-Manager provides both high-level and low-level interfaces for controlling microscopes, which can be used independently or in combination. 

The high-level interface revolves around the :class:`Acquisition<pycromanager.Acquisition>` class, which provides control of common microscopy experiments like acquiring 3D volumes, time series, and multi-channel data. It also supports customization that enables extensions to non-standard hardware and acquisition schemes. The data saved by an :class:`Acquisition<pycromanager.Acquisition>` can be accessed as ``numpy`` or ``dask`` arrays using the :class:`Dataset<pycromanager.Dataset>` class. :class:`Acquisition<pycromanager.Acquisition>` provides its own image viewer, which can be disabled along with the Micro-Manger GUI (see :ref:`headless_mode`), enabling the pycromanager to be used as invisible backend acquisition system for custom applications.

Low-level hardware control is possible through accessing the :ref:`Micro-Manager <core>`. This can be used to do things like, for example, getting/setting the position of an XY stage or focus drive. 

Workflows that utilize existing Micro-manager plugins written in Java or scripts written in `beanshell <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_ can be executed through Python by using the Java-Python translation layer used by Pycro-Manager. Examples are shown in the :ref:`studio_api`, :ref:`calling_custom_java` and :ref:`magellan_api` sections.
 

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_overview
	read_data
	core
	headless_mode
	calling_java
	advanced_usage
