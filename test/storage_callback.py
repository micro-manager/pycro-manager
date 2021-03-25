from pycromanager import Acquisition, multi_d_acquisition_events


def storage_monitor_fn(axes):
    dataset = acq.get_dataset()
    pixels = dataset.read_image(**axes)
    print(pixels)


with Acquisition(directory="/Users/henrypinkard/tmp", name="tcz_acq", debug=False,
                 storage_monitor_callback_fn=None) as acq:
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        order="tcz",
    )
    dataset = acq.get_dataset()
    acq.acquire(events)

