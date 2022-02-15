****************
Features
****************

``pycromanager`` has several options for interacting with micro-manager which can be used independently or in combination.  The high level APIs described in :doc:`acq_overview` are usually the best place to start. They describe how to use the pycromanager :class:`Acquisition<pycromanager.Acquisition>` class to run common "multi-dimensional acquisitions" (i.e. Z-stacks, multiple XY posisitons, etc.), customized ones with additional abitrary axes and hardware settings, or ones generated through the `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ GUI (a Micro-manager plugin for imaging large samples such as tissue sections, whole slides, multi-well plates, etc.). 

:class:`Acquisition<pycromanager.Acquisition>` supports customization such as modifying image data on-the-fly, controlling acquisition in response to data, integrating non-micro-manger supported hardware, running high-speed acquisitions with hardware TTL triggering, and using customized visualization/data saving. The data acquired by :class:`Acquisition<pycromanager.Acquisition>` can be read into ``numpy`` or ``dask`` arrays using the :class:`Dataset<pycromanager.Dataset>`, as described in :ref:`reading_data`.

:class:`Acquisition<pycromanager.Acquisition>` provides its own GUI, but this can be disabled along with the Micro-Manger GUI (see :ref:`headless_mode`), enabling the pycromanager to be used as invisible backend acquisition system for custom applications.

For less complicated experiments (e.g. just snapping images on a camera, moving a single piece of hardware), :doc:`core` might be a good place to start.

Finally, for experiments that require Java-based micro-manager plugins or already work well with existing `beanshell scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_, try :ref:`studio_api`, :ref:`calling_custom_java` or :ref:`magellan_api`.

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_overview
	read_data
	core
	calling_java
