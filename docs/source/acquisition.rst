****************
Acquiring data
****************

Pycro-manager presents several options for data acquisition. The easiest and most powerful is the :doc:`acq_high`. This enable a simple syntax for running arbitrary multi-dimensional acquisitions (e.g. Z-stacks, multiple XY posisitons, etc.), as well as execution of code at different points in the acquisition cycle, and processing/modification of the acquired images/metadata.

For less complicated experiments (e.g. just snapping images on a camera, moving a single piece of hardware), see :doc:`core`.

Finally, for experiments that require Java-based micro-manager plugins or already work well with existing `beanshell scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_, try :doc:`generic_java`.

.. toctree::
	:maxdepth: 3
	:caption: Contents:

	acq_high
	core
	generic_java
	apis