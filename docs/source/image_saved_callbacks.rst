.. _image_saved_callbacks:

**************************
Saved image callbacks
**************************

Saved image callbacks, allow a user-supplied ``image_saved_fn`` to be automatically called by the :class:`Acquisition<pycromanager.Acquisition>` as soon as a new image has been saved. The image can then be read directly from disk in Python. This avoids the speed limitations incurred by image processors. It is also a useful way to implement a custom user interface, because the function will be called each time there is new data and the UI should be updated. Alternatively, it can be used to start post-processing large datasets as soon as they are acquired. 


The ``image_saved_fn`` takes two arguments, ``axes`` and ``dataset``. The first is the describe the unique identifier of the image (``z=0``, ``time=2``, etc.), and the second provides access to the :class:`Dataset<pycromanager.Dataset>` associated with the Acquisition. The pixels of the image that was just saved can be accessed by calling:


.. code-block:: python

    pixels = dataset.read_image(**axes)


Alternatively, a three argument version can be utilized in which the arguments are ``axes``, ``dataset``, and ``event_queue``. The event queue allows new acquisition events to be created in response to images being saved to disk.


A full example of using this feature is below:

.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events,

    def image_saved_fn(axes, dataset):
        pixels = dataset.read_image(**axes)
        # TODO: use the pixels for something, like post-processing or a custom image viewer

    with Acquisition(directory=save_dir, name="tcz_acq",
                    image_saved_fn=image_saved_fn,
                     ) as acq:
        events = multi_d_acquisition_events(
            num_time_points=5,
            z_start=0, z_end=6, z_step=0.4,
        )
        acq.acquire(events)



