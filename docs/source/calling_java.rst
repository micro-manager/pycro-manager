
*********************************************
Calling Java code 
*********************************************



.. _calling_custom_java:

Calling custom Java code
================================================

You can also use the :class:`Bridge<pycromanager.Bridge>` to call your own Java code (such as a micro-manager Java plugin). The construction of an arbitrary Java object is show below using Micro-Magellan as an example:

.. code-block:: python

    from pycromanager import JavaObject

    magellan_api = JavaObject('org.micromanager.magellan.api.MagellanAPI')

    # now call whatever Java methods the object has

If the constructor takes arguments, they can be passed in using:

.. code-block:: python

    java_obj = JavaObject('the.full.classpath.to.TheClass', args=['demo', 30])


In either case, calling ``java_obj.`` and using IPython autocomplete to discover method names can be useful for development. Note that function names will be automatically translated from the camelCase Java convention to the Python convention of underscores between words (e.g. ``setExposure`` becomes ``set_exposure``)

If you want to call a static methods on static Java classes, this can be accomlished with ``JavaClass``:

.. code-block:: python

    java_obj = JavaClass('the.full.classpath.to.TheStaticClass')



.. _studio_api:


Calling Micro-manager Java ("Studio") API 
================================================

``pycromanager`` provides a way to control the Java/Beanshell APIs of micromanager through Python. In some cases it may be run existing `beanshell scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_ with little to no modifcation. Check out the `Java documentation <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmstudio/org/micromanager/Studio.html>`_ for this API for more information. Setting the ``convert_camel_case`` option to ``False`` here may be especially useful, because it keeps the function names in the Java convention of ``camelCaseCapitalization`` rather than automatically converting to the Python convention of ``names_with_underscores``.



.. code-block:: python

    from pycromanager import Studio

    studio = Studio(convert_camel_case=False)

    #now use the studio for something



.. _magellan_api:

Controlling Micro-Magellan
================================================

Micro-Magellan is a plugin for imaging large samples that span multiple fields of view (e.g. tissue sections, whole slides, multi-well plates). It provides a graphical user interface for navigating around samples in X,Y, and Z called "explore acquisitions", as well as features for defining and imaging arbitrarily shaped regions of interest ("Surfaces" and "grids"). More information can be found `here <https://micro-manager.org/wiki/MicroMagellan>`_.

In addition to launching :ref:`magellan_acq_launch`, other aspects of Micro-Magellan can be controlled programatically through Python. 

For example, multiple acquisitions can be created or removed programatically, and have their setting changed:


.. code-block:: python

    from pycromanager import Magellan

    magellan = Magellan()
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



.. _pymm_eventserver:

Receive Micro-Manager events
================================================

If you are interested in receiving/reacting to Micro-Manager internal events (
DefaultAcquisitionStartedEvent, DefaultLiveModeEvent or DataProviderHasNewImageEvent), you can have
a look at the `pymm-eventserver <https://github.com/LEB-EPFL/pymm-eventserver>`_ project. It runs a
plugin in Micro-Manger that catches these events and transfers the information using a ZMQ server
inspired by Pycro-Manager to a client in python. They can then be converted for example to
pyqtSignals that can be subscribed to.
