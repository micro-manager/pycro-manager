.. _headless_mode:

**************************
Headless Mode
**************************

Headless mode allows you to use pycromanager without having to launch Micro-Manager. The :meth:`start_headless<pycromanager.start_headless>` method should be run prior to any other calls. This will launch in the background with only the essential Java components for running the pycro-manager acquisition system, without showing a user interface. It provides a lightweight environment for making use of pycromanager's acquisition engine, which can also be run without a GUI in order to use pycromanager as a hidden backend for custom applications. This could be useful, for example, if you want to implement your own user interface, or run pycromanager from a server environment.


The example below shows headless mode in combination with an saved image callback, which calls a user-defined function whenever new data is written to disk. This setup could be used to replace the pycro-manager viewer with a custom user interface (note the ``show_display=False`` in the acquisition).


.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events, start_headless

    mm_app_path = '/path/to/micromanager'
    config_file = mm_app_path + "/MMConfig_demo.cfg"

    # Start the Java process
    start_headless(mm_app_path, config_file, timeout=5000)

    save_dir = r"C:\Users\henry\Desktop\data"

    def image_saved_fn(axes, dataset):
        pixels = dataset.read_image(**axes)
        # TODO: use the pixels for something, like post-processing or a custom image viewer

    with Acquisition(directory=save_dir, name="tcz_acq", show_display=False,
                    image_saved_fn=image_saved_fn,
                     ) as acq:
        events = multi_d_acquisition_events(
            num_time_points=5,
            z_start=0, z_end=6, z_step=0.4,
        )
        acq.acquire(events)

    # Another way to access to the saved data
    d = acq.get_dataset()


How to install Java for Mac OS
=============================================
Running headless mode is easy on Windows, because the correct version of Java comes bundled with the Micro-Manager installer. However, on Mac OS, this is not the case. As a result, it can be helpful to manually install a compatible version of Java.

This can be done through Python as follows: First install the Python package ``install-jdk``.

.. code-block:: shell

    pip install install-jdk


Then open a python environment and run the following code:

.. code-block:: python

    import jdk
    print(jdk.install('11'))

The location where Java was installed will be printed, which should be something like: ``/Users/pm/.jdk/jdk-11.0.14.1+1``. Next, find the location of the java application on this path, which is likely found by appending ``/Contents/Home/bin/java``.

Now, you're ready to run headless mode with this installed Java version. You just need to pass the location of Java to the ``start_headless`` function:

.. code-block:: python

    java_loc = '/Users/pm/.jdk/jdk-11.0.14.1+1/Contents/Home/bin/java'
    start_headless(mm_app_path, config_file, java_loc=java_loc, timeout=5000)


