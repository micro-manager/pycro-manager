.. _magellan_api:

****************************************************************
Controlling Micro-Magellan
****************************************************************

Micro-Magellan is a plugin for imaging large samples that span multiple fields of view (e.g. tissue sections, whole slides, multi-well plates). It provides a graphical user interface for navigating around samples in X,Y, and Z called "explore acquisitions", as well as features for defining and imaging arbitrarily shaped regions of interest ("Surfaces" and "grids"). More information can be found `here <https://micro-manager.org/wiki/MicroMagellan>`_.

In addition to launching :ref:`magellan_acq_launch`, other aspects of Micro-Magellan can be controlled programatically through Python. 

For example, multiple acquisitions can be created or removed programatically, and have their setting changed:


.. code-block:: python

	from pycromanager import Bridge

	bridge = Bridge()
	#get object representing micro-magellan API
	magellan = bridge.get_magellan()

	#get the first acquisition appearing in the magellan acquisitions list
	acq_settings = magellan.get_acquisition_settings(0)

	#add a new one to the list
	magellan.create_acquisition_settings()
	#remove the one you just added
	magellan.remove_acquisition_settings(1)


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


It is also possible to create Grids for acquisition:

.. code-block:: python

	magellan = bridge.get_magellan()

	#create 3x3 grid centered at 0.0 stage coordinates
	magellan.create_grid('New_grid', 3, 3, 0.0, 0.0)

	#delete it (and anything else)
	magellan.delete_all_grids_and_surfaces()


Or surfaces:

.. code-block:: python

	magellan = bridge.get_magellan()

	test_surface = magellan.create_surface('Test surface')

	#Use the magellan GUI to add interpolation points

	#get the z position of the surface at this XY location
	z_position = test_surface.get_extrapolated_value(5., 200.)


