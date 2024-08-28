.. _control_core:

Low-level Control with MMCore
=============================

Pycro-Manager provides access to the Micro-Manager core via the `mmpycorex <https://github.com/micro-manager/mmpycorex>`_ library. The behavior of the ``Core`` object depends on whether the Python or Java backend is in use (see :ref:`headless_mode`):

- Java backend: Returns an automatically Python-converted version of the Java core object
- Python backend: Returns a direct reference to a `pymmcore <https://github.com/micro-manager/pymmcore>`_ object

While both wrap the same underlying object, there may be slight differences in their APIs.

Receiving Core callbacks (Java backend)
---------------------------------------

The ``Core.get_core_callback(callback_fn)`` is used with the Java backend Core object to set up a callback function that triggers whenever the Core emits a signal (such as when the state of hardware has changed). The callback function should be defined with the following signature:

.. code-block:: python

    def callback_fn(name, *args):
        pass

Where ``name`` is the name of the signal emitted by the Core, and ``args`` are the arguments passed by the signal.

For more information, see `here <https://github.com/micro-manager/mmCoreAndDevices/blob/main/MMCore/CoreCallback.cpp>`_

Discovering Available Functions
-------------------------------

To explore available functions:

1. In IPython, type ``core.`` and press Tab for autocomplete suggestions.
2. Refer to the `Java version of the core API documentation <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html>`_.

.. note::
   Function names are automatically translated from Java's camelCase to Python's snake_case (e.g., ``setExposure`` becomes ``set_exposure``).


.. code-block:: python

    # This example shows how to use pycromanager to interact with the micro-manager core. 
    # Aside from the setup section, each following section can be run independently

    from pycromanager import Core
    import numpy as np
    import matplotlib.pyplot as plt

    #Setup
    # get object representing MMCore
    core = Core()

    #### Calling core functions ###
    exposure = core.get_exposure()


    #### Setting and getting properties ####
    # Here we set a property of the core itself, but same code works for device properties
    auto_shutter = core.get_property('Core', 'AutoShutter')
    core.set_property('Core', 'AutoShutter', 0)


    #### Acquiring images ####
    # The micro-manager core exposes several mechanisms foor acquiring images. In order to
    # not interfere with other pycromanager functionality, this is the one that should be used
    core.snap_image()
    tagged_image = core.get_tagged_image()

    # If using micro-manager multi-camera adapter, use core.getTaggedImage(i), where i is
    # the camera index

    # pixels by default come out as a 1D array. We can reshape them into an image
    pixels = np.reshape(tagged_image.pix,
                            newshape=[tagged_image.tags['Height'], tagged_image.tags['Width']])
    # plot it
    plt.imshow(pixels, cmap='gray')
    plt.show()