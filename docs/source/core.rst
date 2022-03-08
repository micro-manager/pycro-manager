.. _control_core:

**********************************************
Controlling Micro-Manager core
**********************************************

The example below shows how to call the Java bindings for the micro-manager core from Python. Because the core API is discorved at runtime and translated into Python, the easiest way to discover which functions are available is to type ``core.`` and type tab to use IPython autocomplete. Alternatively, the documentation for the Java version of the core API can be found `here <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html>`_. Note that function names will be automatically translated from the camelCase Java convention to the Python convention of underscores between words (e.g. ``setExposure`` becomes ``set_exposure``)

An alternative mechanism for controlling the Micro-Manager core is through [pymmcore](https://github.com/micro-manager/pymmcore/), which exposes an almost identical API (but lacks the many additional features of Pycro-Manager). Pymmcore requires a bit more work in to get a configuration loaded and set up and doesn't have it's own GUI. Unless you have a specialized use case (such as running multiple instances of the core in parallel), it is likely easier to start here. 

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
    #Here we set a property of the core itself, but same code works for device properties
    auto_shutter = core.get_property('Core', 'AutoShutter')
    core.set_property('Core', 'AutoShutter', 0)


    #### Acquiring images ####
    #The micro-manager core exposes several mechanisms foor acquiring images. In order to
    #not interfere with other pycromanager functionality, this is the one that should be used
    core.snap_image()
    tagged_image = core.get_tagged_image()
    #If using micro-manager multi-camera adapter, use core.getTaggedImage(i), where i is
    #the camera index

    #pixels by default come out as a 1D array. We can reshape them into an image
    pixels = np.reshape(tagged_image.pix,
                            newshape=[tagged_image.tags['Height'], tagged_image.tags['Width']])
    #plot it
    plt.imshow(pixels, cmap='gray')
    plt.show()