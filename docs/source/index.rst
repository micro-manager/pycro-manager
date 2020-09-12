.. image:: pycromanager_banner.png
  :width: 600
  :alt: Alternative text

``pycromanager`` is a python package that enables python control of `micro-manager <https://micro-manager.org/>`_ as well as the simple development of customized experiments that invlolve microscope hardware control and/or image processing. More information can be found in the `pre-print <https://arxiv.org/abs/2006.11330>`_. 

``pycromanager`` is built on top of a high-performance data transfer layer that operates between Java (i.e. micro-manager) and Python. This enables both the execution of abitrary Java code as if it were written in Python, and the ability to control micro-manager over a network.



.. figure:: overview_figure.png
   :width: 800
   :alt: Overview of pycro-manager

   Pycro-manager overview. The grey boxes denote the C++ and Java components of μManager, including the GUI, Java APIs, and a hardware abstraction layer that enables generic microscope control code to work on a variety of hardware components. The red box shows Pycro- Manager, which consists of a high speed data transfer layer that can operate within a machine or over a network. This layer enables access to all the existing capabilities of μManager as if they were written in Python, so that they can inter-operate with Python libraries (purple boxes) for hardware control, data visualization, scientific computing, etc.






:doc:`setup`
#############

:doc:`features`
##################

:doc:`apis`
###########

.. toctree::
	:maxdepth: 3
	:caption: Contents:
	:hidden:

	setup
	features
	applications
	apis
	citation
	



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
