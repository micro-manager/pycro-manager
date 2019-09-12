from pygellan.magellan_data import MagellanDataset

data_path =  '/Users/henrypinkard/lymphosight_data/raw_data/2018-6-2 4 hours post LPS/whole LN 3 hour post LPS timelapse restart (5 hours now)_1'
magellan = MagellanDataset(data_path)

# array = magellan.as_stitched_array()
array = magellan.as_array()

