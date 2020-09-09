****************
Features
****************

``pycromanager`` has several options for interacting with micro-manager which can be used independently or in combination. The high level APIs described in :doc:`acq_overview` are usually the best place to start. They describe how to run standard multi-dimensional acquisitions (i.e. Z-stacks, multiple XY posisitons, etc.), customized ones, or ones generated through the `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ GUI. They also support customization such as modifying image data on-the-fly, controlling acquisition in response to data, integrating non-micro-manger supported hardware, and using customized visualization/data saving.

For less complicated experiments (e.g. just snapping images on a camera, moving a single piece of hardware), :doc:`core` might be a good place to start.

Finally, for experiments that require Java-based micro-manager plugins or already work well with existing `beanshell scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_, try :doc:`mm_java_apis` or :doc:`your_own_java`.

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_overview
	core
	mm_java_apis
	magellan_api
	your_own_java
