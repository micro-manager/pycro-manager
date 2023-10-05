from pycromanager import multi_d_acquisition_events, Core, Acquisition, start_headless, stop_headless

mm_app_path = r"C:\Users\henry\Micro-Manager-nightly"
config = mm_app_path + r"\MMConfig_demo.cfg"
start_headless(mm_app_path, config, python_backend=True)

with Acquisition() as acq:
    acq.acquire(multi_d_acquisition_events(num_time_points=10))


print('done')