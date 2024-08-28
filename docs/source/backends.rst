.. _backends:

*******************
Backends
*******************

Overview
=========

Pycro-Manager's high-level API is built upon two mutually exclusive backends, each with unique advantages. Understanding this requires a brief overview of the Micro-Manager architecture.

The Micro-Manager Core, responsible for low-level device control, is implemented in C++. The Core can be wrapped in either Java or Python. The Micro-Manager application, including its GUI, is built in Java on top of the Java wrapper.

Pycro-Manager can communicate with the Micro-Manager Core in two ways: through the Java wrapper (which dynamically translated to Python) or via the Python wrapper. Furthermore, both Java and Python contain Acquisition Engines, which control and automate the image capture process, managing timing, hardware synchronization, and image storage.

The following figure illustrates the components of both Pycro-Manager and Micro-Manager:

.. figure:: pm_arch_full.png
   :alt: Full architecture of Pycro-Manager and Micro-Manager application

Pycro-Manager offers three operational modes, each utilizing different components:

1. **Full Micro-Manager application mode**: Uses the Java backend, providing access to the complete Micro-Manager GUI and all its features.
2. **Headless mode (Java)**: Employs the Java backend without the Micro-Manager GUI.
3. **Headless mode (Python)**: Utilizes the Python backend.

.. figure:: three_backends.png
   :alt: Three ways of running Pycro-Manager

Regardless of the backend, users interact with Pycro-Manager through its Python API. However, the choice of backend may affect performance, depending on the specific use case.

.. note::

    Users of the python backend may also be interested in `ExEngine <https://exengine.readthedocs.io/en/latest/>`_, a newer project which provides a more flexible and powerful module for doing the same things as pycro-manager does, and more.


Performance: Java vs Python Backend
====================================

The main difference between backends is performance. Java-Python communication can be slow (typically less than 100 MB/s). Pycro-Manager is designed to minimize data transfer across this boundary when using the Java backend. For instance, in ``Acquisition``, data is acquired and saved within Java code for maximum speed. The Python backend is advantageous when you need to rapidly process data without saving, such as running a custom Python-based live viewer.

The APIs remain consistent across backends, allowing the same code to be used with either backend. For example, development can begin using the Micro-Manager GUI, and later switch to the Python backend if performance bottlenecks are encountered.



.. _headless_mode:

Headless Mode
==============


Headless mode allows you to use Pycro-manager without having to launch Micro-manager. The :meth:`start_headless<pycromanager.start_headless>` method should be run prior to any other calls. This function launches Micro-Manager core and the acquisition engine, which is used by the ``Acquisition`` class. To shut down the headless mode, call :meth:`stop_headless<pycromanager.stop_headless>`.

Headless mode supports both Java and Python backends. The Java backend uses the same components as the full Micro-Manager application, while the Python backend provides pure Python implementations of these components.

This lightweight environment is ideal for custom applications, such as implementing your own user interface or running Pycro-Manager on a server.

To use headless mode:

.. code-block:: python

    from pycromanager import Core, start_headless, stop_headless
    mm_app_path = '/path/to/micromanager'
    config_file = mm_app_path + "/MMConfig_demo.cfg"

    # Start the headless process (Java backend)
    start_headless(mm_app_path, config_file, python_backend=False)

    # Now use Pycro-Manager APIs as normal
    core = Core()

    # Stop the headless process
    stop_headless()




Installing Java for Mac OS
--------------------------------
Running headless mode with the Java backend is easy on Windows, because the correct version of Java comes bundled with the Micro-Manager installer. However, on Mac OS, this is not the case. As a result, it can be helpful to manually install a compatible version of Java.

This can be done through Python as follows: First install the Python package ``install-jdk``.

.. code-block:: shell

    pip install install-jdk


Then open a python environment and run the following code:

.. code-block:: python

    import jdk
    print(jdk.install('11'))

The location where Java was installed will be printed, which should be something like: ``/Users/pm/.jdk/jdk-11.0.14.1+1``. Next, find the location of the java application on this path, which is likely found by appending ``/Contents/Home/bin/java``.

Now headless mode can be run with this installed Java version by passing the location of Java to the ``start_headless`` function:

.. code-block:: python

    java_loc = '/Users/pm/.jdk/jdk-11.0.14.1+1/Contents/Home/bin/java'
    start_headless(mm_app_path, config_file, java_loc=java_loc, timeout=5000)


