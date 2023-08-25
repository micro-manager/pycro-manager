try:
    from napari.qt import thread_worker
except:
    raise Exception('Napari must be installed to use these features')
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
        if image is not None:
            try:
                viewer.layers['pycromanager acquisition'].data = image
            except KeyError:
                viewer.add_image(image, name='pycromanager acquisition')


    @thread_worker(connect={'yielded': update_layer})
    def napari_signaller():
        """
        Monitor for signals that Acqusition has a new image ready, and when that happens
        update napari appropriately
        """
        while True:
            time.sleep(1 / 60)  # limit to 60 hz refresh
            image = None

            if dataset is not None and dataset.has_new_image():
                # A new image has arrived, this could be overwriting something existing or have a new combination of axes
                image = dataset.as_array()
                shape = np.array([len(dataset.axes[name]) for name in dataset.axes.keys()])
                if not hasattr(napari_signaller, 'old_shape') or \
                        napari_signaller.old_shape.size != shape.size or \
                        np.any(napari_signaller.old_shape != shape):
                    napari_signaller.old_shape = shape

            yield image

    napari_signaller()
