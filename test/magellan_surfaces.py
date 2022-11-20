from pycromanager import _Bridge, Acquisition
import numpy as np

with _Bridge() as bridge:
    # get object representing micro-magellan API
    magellan = bridge.get_magellan()


    ###### Part 3b: find center of surface

    # TODO: create surface in Magellan GUI

    surface = magellan.get_surface("New Surface 1")
    # get the positions of the interpolation points that were manually clicked
    interp_points = surface.get_points()

    # TODO: find the center of tissue from all points below

    # iterate through all points and print their coordinates
    for i in range(interp_points.size()):
        point = interp_points.get(i)
        print(point.x, point.y, point.z)

    # can add points with
    # surface.add_point(x, y, z)


    ### Part 3a run autofocus #####

    # TODO: maybe run an initial focus test to see how off the surface is


    # this function will run after the hardware has been updated (i.e. xy stage moved) but before each image is acquired
    def hook_fn(event):

        # look in the event to see all information about what is being acquired
        print(event)
        # for example:
        coordinates = np.array([event["x"], event["y"], event["z"]])

        # if row and column are each a multiple of 3
        if event["row"] % 3 == 0 and event["col"] % 3:

            # TODO: do some autofocusing calculation, then move z to correct position

            pass

        # store and update focus offset
        if not hasattr(hook_fn, "z_offset"):
            hook_fn.z_offset = 0
        # TODO: update z_offset
        # hook_fn.z_offset +=

        # TODO move to correct position

        return event


# Run the acquisition

# magellan example
acq = Acquisition(magellan_acq_index=0, post_hardware_hook_fn=hook_fn)
acq.await_completion()
