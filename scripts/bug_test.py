from pycromanager import _Bridge

from pycromanager import Acquisition, multi_d_acquisition_events


def img_process_fn(image, metadata):
    # modify the pixels by setting a 100 pixel square at the top left to 0

    image[:100, :100] = 0

    # propogate the image and metadata to the default viewer and saving classes

    return image, metadata


z_shg_center = 0

if __name__ == "__main__":  # this is important, don't forget it

    with Acquisition(
        directory="/Users/henrypinkard/megellandump/",
        name="exp_2_mda",
        image_process_fn=img_process_fn,
    ) as acq:
        events = multi_d_acquisition_events(
            z_start=z_shg_center - 20, z_end=z_shg_center + 20, z_step=5
        )

        acq.acquire(events)

#       acq.acquire()
