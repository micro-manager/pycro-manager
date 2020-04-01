==============
API Reference
==============

High-level acquisition APIs (``pycromanager.acquire``)
#######################################################

.. currentmodule:: pycromanager.acquire
.. autoclass:: Bridge
	:members:
.. autoclass:: Acquisition
	:members:

Reading acquired data (``pycromanager.data``)
##############################################

.. currentmodule:: pycromanager.data


Low-level (micro-manager core) APIs
###################################

The core API is discovered dynamically at runtime, though not every method is implemented. Typing ``core.`` and using autocomplete with ``IPython`` is the best way to discover which functions are available. Documentation on for the Java version of the core API (which ``pycro-manager`` calls) can be found `here <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html>`_.