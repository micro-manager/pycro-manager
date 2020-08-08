import numpy as np
from pycromanager import multi_d_acquisition_events, Acquisition

if __name__ == '__main__':
    # Version 1:
    def img_process_fn(image, metadata):
        image[250:350, 100:300] = np.random.randint(0, 4999)
        # raise Exception()
        return image, metadata

    with Acquisition(directory='/Users/henrypinkard/megllandump', name='tcz_acq', image_process_fn=img_process_fn) as acq:
        # Generate the events for a single z-stack
        events = multi_d_acquisition_events(
            num_time_points=10, time_interval_s=0,
            channel_group='channel', channels=['DAPI', 'FITC'],
            z_start=0, z_end=6, z_step=0.4,
            order='tcz')
        acq.acquire(events)
