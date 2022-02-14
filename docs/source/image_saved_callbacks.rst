.. _image_saved_callbacks:

**************************
Saved image callbacks
**************************

The data is saved in Java but can be read natively in python for faster performance
These get called automatically as soon as an image finishes writing

.. code-block:: python

    def img_process_fn(image, metadata):
		
        from pycromanager import Acquisition, multi_d_acquisition_events,


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



