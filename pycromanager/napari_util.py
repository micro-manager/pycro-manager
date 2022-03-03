from napari.qt import thread_worker
import numpy as np
import time


def start_napari_signalling(viewer, dataset):
    """
    Start up a threadworker, which will check for new images arrived in the dataset
    and then signal to napari to update or refresh as needed
    :param viewer: the napari Viewer
    :param dataset: the Datatset being acquired
    :return:
    """

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
            if dataset is not None and hasattr(dataset, 'new_image_arrived') and dataset.new_image_arrived:
                dataset.new_image_arrived = False
                # A new image has arrived, but we only need to regenerate the dask array
                # if its shape has changed
                shape = np.array([len(dataset.axes[name]) for name in dataset.axes.keys()])
                if not hasattr(napari_signaller, 'old_shape') or \
                        napari_signaller.old_shape.size != shape.size or \
                        np.any(napari_signaller.old_shape != shape):
                    image = dataset.as_array()
                    napari_signaller.old_shape = shape
                    yield image
                else:
                    # Tell viewer to update but not change data
                    yield None
            else:
                time.sleep(1 / 60) # 60 hz refresh


    napari_signaller()
