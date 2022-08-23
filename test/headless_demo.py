from pycromanager import Acquisition, multi_d_acquisition_events, Core, start_headless
import numpy as np
import time

mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
# mm_app_path = 'C:/Program Files/Micro-Manager-2.0gamma'

config_file = mm_app_path + "/MMConfig_demo.cfg"

#Optional: specify your own version of java to run with
java_loc = "/Library/Java/JavaVirtualMachines/zulu-8.jdk/Contents/Home/bin/java"
# java_loc = r"C:\Users\henry\.jdk\jdk8u322-b06\jre\bin\java.exe"
# java_loc = None
start_headless(mm_app_path, config_file, java_loc=java_loc, timeout=5000)

core = Core()
core.snap_image()
print(core.get_image())

save_dir = "/Users/henrypinkard/tmp"
# save_dir = r"C:\Users\henry\Desktop\datadump"


def image_saved_fn(axes, dataset):
    pixels = dataset.read_image(**axes)
    print(np.mean(pixels))

with Acquisition(directory=save_dir, name="tcz_acq", show_display=True,
                image_saved_fn=image_saved_fn
                 ) as acq:
    # Generate the events for a single z-stack
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        channel_group="Channel",
        channels=["DAPI", "FITC"],
        z_start=0,
        z_end=6,
        z_step=0.4,
        order="tcz",
    )
    acq.acquire(events)
d = acq.get_dataset()
pass