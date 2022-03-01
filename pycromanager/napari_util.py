from napari.qt import thread_worker
import numpy as np
import time



def get_napari_signaller(viewer):

    def image_saved_callback(axes, d):
        """
        Callback function that will be used to signal to napari that a new image is ready
        """
        image_saved_callback.dataset = d
        d.update_ready = True

    def get_dataset_fn():
        if hasattr(image_saved_callback, 'dataset'):
            return image_saved_callback.dataset
        return None

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
    def napari_signaller():
        """
        Monitor for signals that Acqusition has a new image ready, and when that happens
        update napari appropriately
        """
        while True:
            dataset = get_dataset_fn()
            if dataset is not None and hasattr(dataset, 'update_ready') and dataset.update_ready:
                dataset.update_ready = False
                # A new image has arrived, but we only need to regenerate the dask array
                # if its shape has changed
                shape = np.array([len(dataset.axes[name]) for name in dataset.axes.keys()])
                if not hasattr(napari_signaller, 'old_shape') or \
                        napari_signaller.old_shape.size != shape.size or \
                        np.any(napari_signaller.old_shape != shape):
                    image = np.array(dataset.as_array())
                    napari_signaller.old_shape = shape
                    yield image
                else:
                    # Tell viewer to update but not change data
                    yield None
            else:
                time.sleep(1 / 60) # 60 hz refresh


    return napari_signaller, image_saved_callback