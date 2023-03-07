from pycromanager import ExploreAcquisition, Core

# core = Core()

def image_process_fn(image, metadata):
    image[20:60, 20:60] = 0
    return image, metadata

ExploreAcquisition('/Users/henrypinkard/tmp', 'explore_test', 2, (0, 0), 'Channel', image_process_fn=image_process_fn)