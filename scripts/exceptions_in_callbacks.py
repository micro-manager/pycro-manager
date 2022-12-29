from pycromanager import Core, Acquisition, multi_d_acquisition_events, start_headless
import time

mm_app_path = 'C:/Program Files/Micro-Manager-2.0'
config_file = mm_app_path + "/MMConfig_demo.cfg"
# start_headless(mm_app_path, config_file, debug=True)

# mmc = Core()
# mmc.set_property('Z', 'UseSequences', 'Yes')

def hook_fn(event):
    if not hasattr(hook_fn, "i"):
        hook_fn.i = 0
    hook_fn.i += 1
    if hook_fn.i == 8:
        raise Exception("sdfsdf")
    return event


def img_proc_fn(image, metadata):
    if not hasattr(img_proc_fn, "i"):
        img_proc_fn.i = 0
    img_proc_fn.i += 1
    if img_proc_fn.i == 3:
        raise Exception("asdfasdf")
    return image, metadata

with Acquisition(directory=r"C:\Users\henry\Desktop\datadump", name='PM_test2',
                 pre_hardware_hook_fn=hook_fn,
                 #    image_process_fn=img_proc_fn,
                 debug=True, timeout=4000) as acq:
    acq.acquire(multi_d_acquisition_events(num_time_points=4, time_interval_s=5, z_start = 0, z_end = 3, z_step = 1))

acq = None
pass