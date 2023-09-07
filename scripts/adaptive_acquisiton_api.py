from pycromanager import Acquisition, multi_d_acquisition_events, AcqNotification
import time
import numpy as np

events = multi_d_acquisition_events(num_time_points=10, time_interval_s=0)

print_notification_fn = lambda x: print(x.to_json())

start = time.time()
with Acquisition(directory='C:\\Users\\henry\\Desktop\\data', name='acq', notification_callback_fn=print_notification_fn,
                 show_display=False) as acq:
    start = time.time()
    future = acq.acquire(events)

    future.await_execution({'time': 5}, AcqNotification.Hardware.POST_HARDWARE)
    print('time point 5 post hardware')

    image = future.await_image_saved({'time': 5}, return_image=True)
    print('time point 5 image saved ', time.time() - start, '\t\tmean image value: ', np.mean(image))

    images = future.await_image_saved([{'time': 7}, {'time': 8}, {'time': 9}], return_image=True)
    assert (len(images) == 3)
    for image in images:
        print('mean of image in stack: ', np.mean(image))

# Make sure the returned images were the correct ones
on_disk = [acq.get_dataset().read_image(time=t) for t in [7, 8, 9]]
assert all([np.all(on_disk[i] == images[i]) for i in range(3)])

