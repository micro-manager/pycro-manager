from pycromanager import multi_d_acquisition_events, Acquisition, start_headless, stop_headless

mm_app_path = r"C:\Users\henry\Micro-Manager-nightly"
config = mm_app_path + r"\MMConfig_demo.cfg"
start_headless(mm_app_path, config)

def print_notification_fn(acq_notification):
    print(acq_notification.to_json())

with Acquisition(directory=r"C:\Users\henry\Desktop\data",
                    notification_callback_fn=print_notification_fn,
                 ) as acq:
    acq.acquire(multi_d_acquisition_events(num_time_points=10))

stop_headless()
print('done')