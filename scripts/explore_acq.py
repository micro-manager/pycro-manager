from pycromanager import ExploreAcquisition, Core

# core = Core()

def image_process_fn(image, metadata):
    image[20:60, 20:60] = 0
    return image, metadata

def image_saved_callback(axes, dataset):
    print(axes)
    print(dataset.read_image(**axes))

ExploreAcquisition('/Users/henrypinkard/Desktop', 'explore_no_channels', 2, (0, 0), None,
                   image_saved_fn=image_saved_callback,
                   image_process_fn=image_process_fn)