.. image:: pycromanager_banner.png
  :width: 600
  :alt: Alternative text

``pycromanager`` is a python package that enables control of `micro-manager <https://micro-manager.org/>`_ as well as the simple development of customized experiments that involve microscope hardware control integrated with real-time image processing. More information can be found in the `pre-print <https://arxiv.org/abs/2006.11330>`_. 


.. figure:: overview_figure.png
   :width: 800
   :alt: Overview of pycro-manager

   **Pycro-manager architecture overview.** (Grey) The existing parts of µManager provide generic microscope control abstracted from specific hardware, a graphical user interface (GUI), a Java plugin interface, and an acquisition engine, which automates various aspects of data collection. (Orange) Pycro-Manager enables access to these components through Python over a network-compatible transport layer, as well as a concise, high-level programming interface for acquiring data. These provide integration of data acquisition with  (purple) Python libraries for hardware control, data visualization, scientific computing, etc. 





.. ***********************
.. :doc:`setup`
.. ***********************

.. ***********************
.. :doc:`features`
.. ***********************

.. ***********************
.. :doc:`applications`
.. ***********************

.. ***********************
.. :doc:`apis`
.. ***********************

.. toctree::
	:maxdepth: 1
	:caption: Contents:

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
