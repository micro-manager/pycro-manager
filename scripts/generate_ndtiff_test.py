from pycromanager import Acquisition, multi_d_acquisition_events, Core, start_headless, XYTiledAcquisition
import numpy as np
import time

# mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
# mm_app_path = 'C:/Program Files/Micro-Manager-2.0gamma'

# config_file = mm_app_path + "/MMConfig_demo.cfg"

#Optional: specify your own version of java to run with
java_loc = "/Library/Java/JavaVirtualMachines/zulu-8.jdk/Contents/Home/bin/java"
# java_loc = r"C:\Users\henry\.jdk\jdk8u322-b06\jre\bin\java.exe"
# java_loc = None
# start_headless(mm_app_path, config_file, java_loc=java_loc, timeout=5000)

core = Core()

#small images to save data
core.set_property("Camera", "OnCameraCCDXSize", 32)
core.set_property("Camera", "OnCameraCCDYSize", 32)

save_dir = "/Users/henrypinkard/tmp"
# save_dir = r"C:\Users\henry\Desktop\datadump"



with Acquisition(directory=save_dir, name="ndtiffv3.0_test", show_display=True,
                 ) as acq:
    # Generate the events for a single z-stack
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        channel_group="Channel",
        channels=["DAPI", "FITC"],
        order="tc",
    )
    acq.acquire(events)
d = acq.get_dataset()
# # pass


with XYTiledAcquisition(directory=save_dir, name="ndtiffv3.0_stitched_test", tile_overlap=4
                 ) as acq:
    acq.acquire({'row': 1, 'col': 1})
    acq.acquire({'row': 0, 'col': 0})

d = acq.get_dataset()
# pass