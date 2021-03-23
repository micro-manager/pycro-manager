from pycromanager import Acquisition, multi_d_acquisition_events, Bridge, start_headless

mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
config_file = "/Applications/Micro-Manager-2.0.0-gamma1/MMConfig_demo.cfg"

start_headless(mm_app_path, config_file)

b = Bridge()
b.get_core().snap_image()
print(b.get_core().get_image())

with Acquisition(directory="/Users/henrypinkard/tmp", name="tcz_acq", debug=True) as acq:
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
