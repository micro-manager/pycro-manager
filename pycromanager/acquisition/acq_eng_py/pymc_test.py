import os.path
import json

import pymmcore

from pycromanager import start_headless, Core

mm_dir = "C:/Program Files/Micro-Manager-2.0"

start_headless(mm_dir, backend="python")

core = Core()

class TaggedImage:

    def __init__(self, tags, pix):
        self.tags = tags
        self.pix = pix

def pop_next_tagged_image(self):
    pix = self.popNextImage()
    print('got image')
    md = pymmcore.Metadata()
    core.pop_next_image_md(0, 0, md)
    tags = {key: md.GetSingleTag(key).GetValue() for key in md.GetKeys()}
    return TaggedImage(tags, pix)

def get_tagged_image(self, cam_index, camera, height, width, binning=None, pixel_type=None, roi_x_start=None, roi_y_start=None):
    """
    Different signature than the Java version because of difference in metadata handling in the swig layers
    """
    pix = self.get_image()
    md = pymmcore.Metadata()
    # most of the same tags from pop_next_tagged_image, which may not be the same as the MMCoreJ version of this function
    tags = { 'Camera': camera, 'Height': height, 'Width': width, 'PixelType': pixel_type, 'CameraChannelIndex': cam_index }
    # Could optionally add these for completeness but there might be a performance hit
    if binning is not None:
        tags['Binning'] = binning
    if roi_x_start is not None:
        tags['ROI-X-start'] = roi_x_start
    if roi_y_start is not None:
        tags['ROI-Y-start'] = roi_y_start

    return TaggedImage(tags, pix)

N = 5
core.start_sequence_acquisition(N, 0, False)


i = 0
while i < N:
    try:
        ti = pop_next_tagged_image(core)
    except:
        continue
    i += 1
    print(i)



# core.snap_image()
# ti = get_tagged_image(core, 0,1 ,1,1)

pass
# core.pop_next_tagged_image()
# core.get_tagged_image(cam_index)



# # mmc.snapImage()
# # mmc.getImdage()
# md = pymmcore.Metadata()
# mmc.getLastImageMD(0, 0, md)
# {key: md.GetSingleTag(key).GetValue() for key in md.GetKeys()}

