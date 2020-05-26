from pycromanager import Acquisition

if __name__ == '__main__':

    with Acquisition('/Users/henrypinkard/megllandump', 'tiled', tile_overlap=10) as acq:
        #10 pixel overlap between adjacent tiles

        acq.acquire({'row': 0, 'col': 0})
        acq.acquire({'row': 1, 'col': 0})
        acq.acquire({'row': 0, 'col': 1})

        dataset = acq.get_dataset()
        dataset.has_image(row=0, col=0, resolution_level=1)
        dataset.read_image(row=0, col=0, resolution_level=1)
