from pycromanager import Acquisition, multi_d_acquisition_events


def image_saved_fn(axes, dataset):
    pixels = dataset.read_image(**axes)
    # Do something with image pixels/metadata


dir = "/Users/henrypinkard/tmp/"
with Acquisition(directory=dir, name="tcz_acq", debug=False, image_saved_fn=image_saved_fn) as acq:
    events = multi_d_acquisition_events(
        num_time_points=5,
        time_interval_s=0,
        order="tcz",
    )
    acq.acquire(events)
