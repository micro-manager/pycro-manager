from pycromanager import Bridge, Acquisition
import numpy as np

bridge = Bridge()
# get object representing micro-magellan API
magellan = bridge.get_magellan()


def hook_fn(event):
    coordinates = np.array([event["x"], event["y"], event["z"]])

    return event


if __name__ == "__main__":
    # magellan example
    acq = Acquisition(magellan_acq_index=0, post_hardware_hook_fn=hook_fn)
    acq.await_completion()

pass
