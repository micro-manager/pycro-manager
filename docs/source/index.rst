.. image:: pycromanager_banner.png
  :width: 600
  :alt: Alternative text

``pycromanager`` is a python package that enables python control of `micro-manager <https://micro-manager.org/>`_ as well as the simple development of customized experiments that invlolve microscope hardware control and/or image processing. More information can be found in the `pre-print <https://arxiv.org/abs/2006.11330>`_. 


.. figure:: overview_figure.png
   :width: 800
   :alt: Overview of pycro-manager

   **Pycro-manager overview.** The grey boxes denote the C++ and Java components of µManager, including the GUI, Java APIs, and a hardware abstraction layer that enables generic microscope control code to work on a variety of hardware components. The red box shows Pycro-Manager, which is built upon a high speed data transfer layer that can operate within a machine or over a network. This layer enables access to the existing capabilities of µManager as if they were written in Python. In addition, a new Acquisition API provides powerful automation of data collection combined with easy ways to inter-operate with Python libraries (purple boxes) for hardware control, data visualization, scientific computing, etc.





***********************
:doc:`setup`
***********************

***********************
:doc:`features`
***********************

***********************
:doc:`applications`
***********************

***********************
:doc:`apis`
***********************

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
