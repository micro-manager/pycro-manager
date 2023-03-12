from pycromanager import XYTiledAcquisition, multi_d_acquisition_events


def event_edit_fn(event):
    # row = event["row"]
    # col = event["col"]

    # TODO: if you want to cancel, dont return anything

    return event


def image_callback_fn(image, metadata):
    row = metadata["Axes"]["row"]
    col = metadata["Axes"]["column"]
    channel = metadata["Axes"]["channel"]
    # other image axes (e.g. a z axis). 'position' axis is redundant to row and column indices
    axes = metadata["Axes"]
    # numpy array
    image

    # TODO: run callback function

    return image, metadata


with XYTiledAcquisition(
    directory=r"/Users/henrypinkard/tmp/",
    name="tiled",
    tile_overlap=10,
    image_process_fn=image_callback_fn,
    pre_hardware_hook_fn=event_edit_fn,
    debug=False,
) as acq:
    # 10 pixel overlap between adjacent tiles
    acq.acquire({'axes': {
                     "row": 0, "column": -1, "channel": 'green'
                        },
                 "config_group": ("Channel", "FITC")})
    acq.acquire({'axes': {
                     "row": 0, "column": 0, "channel": 'green'
                        },
                 "config_group": ("Channel", "FITC")})
    acq.acquire({'axes': {
                     "row": 0, "column": 1, "channel": 'green'
                        },
                 "config_group": ("Channel", "FITC")})
