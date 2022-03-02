"""
Use the Acquisition class with Napari as an image viewer. This is tested in an IDE.
In other python environments (i.e. notebook), the relevant calls to napari might be different
"""
from pycromanager import start_headless
from pycromanager import Acquisition, multi_d_acquisition_events
from napari.qt.threading import thread_worker
import threading
import napari
import numpy as np
import time

# Optional: start pycro-manager in headless mode
mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
config_file = mm_app_path + "/MMConfig_demo.cfg"
java_loc = "/Users/henrypinkard/.jdk/jdk-11.0.14.1+1/Contents/Home/bin/java"
start_headless(mm_app_path=mm_app_path, config_file=config_file, java_loc=java_loc, timeout=5000)


dataset = None
update_ready = False

def image_saved_callback(axes, d):
    """
    Callback function that will be used to signal to napari that a new image is ready
    """
    global dataset
    global update_ready
    if dataset is None:
        dataset = d
    update_ready = True

# This function will run an acquisition on a different thread (because calling
# napari.run() will block on this thread
def run_acq():
    with Acquisition(directory="/Users/henrypinkard/tmp", name="tcz_acq",
                     image_saved_fn=image_saved_callback, show_display=False) as acq:
        events = multi_d_acquisition_events(
            num_time_points=10, time_interval_s=5,
            channel_group="Channel", channels=["DAPI", "FITC"],
            z_start=0, z_end=6, z_step=0.7,
            order="tcz",
        )
        acq.acquire(events)


viewer = napari.Viewer()

def update_layer(image):
    """
    update the napari layer with the new image
    """
    if len(viewer.layers) == 0:
        viewer.add_image(image)
    elif image is None:
        viewer.layers[0].refresh()
    else:
        viewer.layers[0].data = image


@thread_worker(connect={'yielded': update_layer})
def update_images():
    """
    Monitor for signals that Acqusition has a new image ready, and when that happens
    update napari appropriately
    """
    global update_ready
    while True:
        if update_ready:
            update_ready = False
            # A new image has arrived, but we only need to regenerate the dask array
            # if its shape has changed
            shape = np.array([len(dataset.axes[name]) for name in dataset.axes.keys()])
            if not hasattr(update_images, 'old_shape') or \
                    update_images.old_shape.size != shape.size or \
                    np.any(update_images.old_shape != shape):
                image = np.array(dataset.as_array())
                update_images.old_shape = shape
                yield image
            else:
                # Tell viewer to update but not change data
                yield None
        else:
            time.sleep(1 / 60) # 60 hz refresh


# start the updater function
update_images()
# run the acquisisiton
threading.Thread(target=run_acq).start()
# start napari
napari.run()