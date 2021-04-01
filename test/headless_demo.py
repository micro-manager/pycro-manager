from pycromanager import Acquisition, multi_d_acquisition_events, Bridge, start_headless

mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
# mm_app_path = 'C:/Program Files/Micro-Manager-2.0gamma'

config_file = mm_app_path + "/MMConfig_demo.cfg"

#Optional: specify your own version of java to run with
java_loc = "/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java"
# java_loc = None
start_headless(mm_app_path, config_file, java_loc=java_loc)

b = Bridge()
b.get_core().snap_image()
print(b.get_core().get_image())

save_dir = "/Users/henrypinkard/tmp"
# save_dir = "C:/Users/Henry Pinkard/Desktop/datadump"

with Acquisition(directory=save_dir, name="tcz_acq", debug=True) as acq:
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
