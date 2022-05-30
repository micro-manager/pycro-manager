from pycromanager import Acquisition, multi_d_acquisition_events


def img_process(image, metadata):
    print(metadata['Axes'])
    # TODO: process and save images.


with Acquisition(image_process_fn=img_process) as acq:
    events = multi_d_acquisition_events(num_time_points=2, time_interval_s=0.1)
    acq.acquire(events)
