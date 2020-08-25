from pycromanager import Acquisition, multi_d_acquisition_events

if __name__ == '__main__':
    def event_edit_fn(event):
        row = event['row']
        col = event['col']

        # TODO: if you want to cancel, dont return anything

        return event


    def image_callback_fn(image, metadata):
        row = metadata['GridRowIndex']
        col = metadata['GridColumnIndex']
        channel = metadata['Channel']
        # other image axes (e.g. a z axis). 'position' axis is redundant to row and column indices
        axes = metadata['Axes']
        # numpy array
        image

        # TODO: run callback function

        return image, metadata


    with Acquisition('/Users/henrypinkard/megllandump', 'tiled', tile_overlap=10,
                     image_process_fn=image_callback_fn,
                     pre_hardware_hook_fn=event_edit_fn) as acq:
        # 10 pixel overlap between adjacent tiles

        acq.acquire({'row': 0, 'col': 0, 'channel': {'group': 'channel', 'config': 'DAPI'}})
        acq.acquire({'row': 0, 'col': 0, 'channel': {'group': 'channel', 'config': 'FITC'}})
        acq.acquire({'row': 1, 'col': 0, 'channel': {'group': 'channel', 'config': 'DAPI'}})
        acq.acquire({'row': 1, 'col': 0, 'channel': {'group': 'channel', 'config': 'FITC'}})
        acq.acquire({'row': 0, 'col': 1, 'channel': {'group': 'channel', 'config': 'DAPI'}})
        acq.acquire({'row': 0, 'col': 1, 'channel': {'group': 'channel', 'config': 'FITC'}})