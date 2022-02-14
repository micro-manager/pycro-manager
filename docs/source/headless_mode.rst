.. _headless_mode:

**************************
Headless Mode
**************************

Headless mode allows you to launch pycromanager directly from Python without having to open the Micro-Manager GUI. 

It only runs the minimal libraries for PM acquisitions and core

You can combine this with turning off the PM image viewer to implement your own image viewers/user interfaces that use pycromanager as a backend



.. code-block:: python

    def img_process_fn(image, metadata):
		
        from pycromanager import Acquisition, multi_d_acquisition_events, Bridge, start_headless
        import numpy as np

        mm_app_path = '/path/to/micromanager'
        config_file = mm_app_path + "/MMConfig_demo.cfg"

        # If on Mac OS you need to specify the Java location.
        # On windows java is bundled with micro-manager and this is
        # inferred from the micro-manager install directory 
        # java_loc = "/Users/PM/.jdk/jdk-11.0.14.1+1/Contents/Home/bin/java"
        java_loc = None

        # Start the Java process
        start_headless(mm_app_path, config_file, java_loc=java_loc, timeout=5000)

        # save_dir = "/Users/henrypinkard/tmp"
        save_dir = r"C:\Users\henry\Desktop\datadump"

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


