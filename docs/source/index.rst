.. image:: pycromanager_banner.png
  :width: 600
  :alt: Alternative text

``pycromanager`` is a python package for controlling different parts of `micro-manager <https://micro-manager.org/>`_ using Python. It is designed for maximum flexibility, in order to serve as a useful building block for "smart" microscopes that use feedback from data or external istrumentation to control the process of acquiring data. 

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
