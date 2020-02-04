from pygellan.acquire import PygellanBridge
import os

#establish communication with Magellan
bridge = PygellanBridge()
#get object representing micro-magellan API
magellan = bridge.get_magellan()

acquistions = magellan.get_acquisitions()
#grab the first acquisition in the list
acq = acquistions[0]
acq_settings = acq.get_acquisition_settings()

#Edit the acquisition's settings (i.e. same thing as the controls in the magellan GUI)
#Below is a comprhensive list of all possible settings that be changed. In practice
#only a subset of them will need to be explicitly called

#saving name and path
acq_settings.set_acquisition_name('experiment_1')
acq_settings.set_saving_dir('{}path{}to{}dir'.format(os.sep, os.sep, os.sep))
acq_settings.set_tile_overlap_percent(5)

#time settings
acq_settings.set_time_enabled(True)
acq_settings.set_time_interval(9.1, 's') # 'ms', 's', or 'min'
acq_settings.set_num_time_points(20)

#channel settings
acq_settings.set_channel_group('Channel')
acq_settings.set_use_channel('DAPI', False) #channel_name, use
acq_settings.set_channel_exposure('DAPI', 5.0) #channel_name, exposure in ms
acq_settings.set_channel_z_offset('DAPI', -0.5) #channel_name, offset in um

#space settings
# '3d_cuboid', '3d_between_surfaces', '3d_distance_from_surface', '2d_flat', '2d_surface'
acq_settings.set_acquisition_space_type('3d_cuboid')
acq_settings.set_xy_position_source('New Surface 1')
acq_settings.set_z_step(4.5)
acq_settings.set_surface('New Surface 1')
acq_settings.set_bottom_surface('New Surface 1')
acq_settings.set_top_surface('New Surface 1')
acq_settings.set_z_start(4.1)
acq_settings.set_z_end(10.1)


acq.start()


