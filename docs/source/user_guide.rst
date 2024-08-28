****************
User Guide
****************

Starting Micro-Manager
======================

After completing the :ref:`setup`, Pycro-Manager offers two running modes:

1. Alongside Micro-Manager's desktop application. This is recommended for new users, as it provides access to the Micro-Manager GUI for microscope configuration and hardware testing.

2. :ref:`headless_mode`, where the Micro-Manager Core is launched programmatically without the desktop application.

The :ref:`backends` page provides more information on pycro-manager's architecture and headless mode (which is not required for most users).

.. toctree::
   :maxdepth: 2
   :hidden:

   backends


High-level APIs
====================

The :class:`Acquisition<pycromanager.Acquisition>` class provides the best starting point for most users. It offers:

- Control of common microscopy experiments (3D volumes, time series, multi-channel data)
- Customization for non-standard hardware and acquisition schemes
- Data access via the :class:`Dataset<pycromanager.Dataset>` class as ``numpy`` or ``dask`` arrays
- A built-in image viewer (which can be disabled for custom applications)

For more information, see :ref:`acq_overview`.

.. toctree::
   :maxdepth: 2
   :hidden:

   acq_overview

Low-level APIs
===================

The Micro-Manager Core allows direct hardware control, such as:

- Getting/setting XY stage or focus drive positions
- Snapping a single image on a camera

For more information, see :ref:`control_core`.

.. toctree::
   :maxdepth: 2
   :hidden:

   core

Java Control Through Python
===========================

In addition to the Python interfaces, Pycro-Manager can call Java code from Python (using the `PyJavaZ library <https://github.com/PyJavaZ/PyJavaZ>`_). This offers:

1. **Micro-Manager UI Control**: Interact with the Micro-Manager user interface programmatically through the :ref:`studio_api`.

2. **Plugin Support**: Control Micro-Manager plugins, such as Micro-Magellan, from Python. See :ref:`magellan_api` for more information.

3. **Legacy Script Compatibility**: Run existing `Micro-Manager scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_ written in Beanshell with minimal modifications.

4. **Custom Java Integration**: Incorporate your own Java code into Python workflows. See :ref:`calling_custom_java` for details.


.. toctree::
   :maxdepth: 2
   :hidden:

   calling_java

