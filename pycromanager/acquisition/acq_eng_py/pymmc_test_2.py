from pymmcore import CMMCore
import os

mm_app_path = "C:/Program Files/Micro-Manager-2.0/"

core = CMMCore()
core.setDeviceAdapterSearchPaths([mm_app_path])
core.loadSystemConfiguration(os.path.join(mm_app_path, "MMConfig_demo.cfg"))

N = 5
core.startSequenceAcquisition(N, 0, False)


i = 0
while i < N:
    try:
        core.popNextImage()
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

