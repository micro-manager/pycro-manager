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
        Monitor for signals that Acquisition has a new image ready, and when that happens
        update napari appropriately
        """
        # don't update faster than the display can handle
        min_update_time = 1 / 30
        last_update_time = time.time()
        while True:
            dataset_writing_complete = dataset.is_finished()
            new_image_ready = dataset.await_new_image(timeout=.25)
            if not new_image_ready:
                continue
            image = dataset.as_array()
            update_time = time.time()
            yield image
            if dataset_writing_complete:
                break
            if update_time - last_update_time < min_update_time:
                time.sleep(min_update_time - (update_time - last_update_time))
            last_update_time = time.time()

    napari_signaller()
