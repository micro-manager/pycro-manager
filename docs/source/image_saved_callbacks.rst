.. _image_saved_callbacks:

**************************
Saved image callbacks
**************************

Saved image callbacks provide a mechanism to execute custom code immediately after an image is saved, which:

1. Avoids speed limitations of image processors when using the Java backend (see :ref:`headless_mode`)
2. Enables custom user interface updates
3. Allows immediate post-processing of acquired data


Basic Usage
-----------

To use saved image callbacks, supply an ``image_saved_fn`` to the :class:`Acquisition<pycromanager.Acquisition>`. This function takes two arguments:

- ``axes``: A dictionary describing the unique identifier of the image (e.g., ``z=0``, ``time=2``)
- ``dataset``: A :class:`Dataset<pycromanager.Dataset>` object associated with the Acquisition

Access the newly saved image as follows:

.. code-block:: python

    def image_saved_fn(axes, dataset):
        pixels = dataset.read_image(**axes)
        # Process or display pixels here


Example:

.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events

    def image_saved_fn(axes, dataset):
        pixels = dataset.read_image(**axes)
        # TODO: Use pixels for post-processing or custom visualization

    with Acquisition(directory=save_dir, name="tcz_acq",
                     image_saved_fn=image_saved_fn) as acq:
        events = multi_d_acquisition_events(
            num_time_points=5,
            z_start=0, z_end=6, z_step=0.4,
        )
        acq.acquire(events)



Adapting acquisition from image saved callbacks
-----------------------------------------------

.. note::

    Adapting acquisition form image saved callbacks is an older feature. The newer :ref:`adaptive_acq` API is now the reccomended way to do this. However, the approach below still works.

The ``event_queue`` allows you to create new acquisition events in response to saved images, enabling adaptive acquisition strategies. Use a three-argument version of ``image_saved_fn``:

.. code-block:: python

    def image_saved_fn(axes, dataset, event_queue):
        pixels = dataset.read_image(**axes)
        # Process pixels
        new_event = create_new_event(pixels)  # Create a new acquisition event
        event_queue.put(new_event)  # Add the new event to the queue



Custom user interface updates
-----------------------------


The example below shows :ref:`headless_mode` in combination with an saved image callback, which calls a user-defined function whenever new data is stored (on disk or in RAM depending on the arguments to ``Acquisition``). This setup could be used to replace the pycro-manager viewer with a custom user interface (note the ``show_display=False`` in the acquisition).


.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events, start_headless

    mm_app_path = '/path/to/micromanager'
    config_file = mm_app_path + "/MMConfig_demo.cfg"

    # Start the Java process
    start_headless(mm_app_path, config_file, timeout=5000)

    save_dir = r"\path\to\data"

    def image_saved_fn(axes, dataset):
        pixels = dataset.read_image(**axes)
        # TODO: use the pixels for something, like post-processing or a custom image viewer

    with Acquisition(directory=save_dir, name="tcz_acq", show_display=False,
                    image_saved_fn=image_saved_fn) as acq:
        events = multi_d_acquisition_events(num_time_points=5,
            z_start=0, z_end=6, z_step=0.4,)
        acq.acquire(events)

    # Another way to access to the saved data
    d = acq.get_dataset()
