.. image:: pycromanager_banner.png
  :width: 600
  :alt: Alternative text

``pycromanager`` is a python package that enables python control of `micro-manager <https://micro-manager.org/>`_ as well as the simple development of customized experiments that invlolve microscope hardware control and/or image processing. More information can be found in the `pre-print <https://arxiv.org/abs/2006.11330>`_. 

``pycromanager`` is built on top of a high-performance data transfer layer that operates between Java (i.e. micro-manager) and Python. This enables both the execution of abitrary Java code as if it were written in Python, and the ability to control micro-manager over a network.

:doc:`setup`
#############

:doc:`tutorials`
##################

:doc:`apis`
###########

.. toctree::
	:maxdepth: 3
	:caption: Contents:
	:hidden:

	setup
	tutorials
	examples
	apis



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
