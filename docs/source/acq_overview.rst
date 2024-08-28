.. _acq_overview:

******************************************************
Acquisitions 
******************************************************

Basic usage
===========



The :class:`Acquisition<pycromanager.Acquisition>` class in Pycro-Manager supports a wide range of microscopy experiments. Its core functions are:

1. Parse user-defined "acquisition events"
2. Control microscope hardware based on these events
3. Efficiently retrieve, save, and provide access to camera image data


Here's a minimal example that acquires a sequence of 5 images:

.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events

    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
        events = multi_d_acquisition_events(num_time_points=5)
        acq.acquire(events)

Alternatively, if you don't provide a ``directory`` and ``name``, the acquired data will be stored in RAM instead of being saved to disk.

Multi-Dimensional Acquisitions
```````````````````````````````

Pycro-Manager supports "multi-dimensional acquisitions" across time, z-stack, channel, and xy position axes, using
the :ref:`multi_d_acq_events` function. More information about the usage of this function can be found in the `MDA Tutorial <multi-d-acq-tutorial.ipynb>`_


Here's an example that acquires a 4D dataset with 4 time points, 6 z-planes, and 2 channels:

.. code-block:: python

    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
        events = multi_d_acquisition_events(
            num_time_points=4, time_interval_s=0,
            channel_group='Channel', channels=['DAPI', 'FITC'],
            z_start=0, z_end=6, z_step=0.4,
            order='tcz')
        acq.acquire(events)

.. toctree::
   :maxdepth: 1
   :hidden:

   multi-d-acq-tutorial.ipynb


Reading Data
============

Acquired data can be accessed programmatically using a :class:`Dataset<pycromanager.Dataset>` object:

.. code-block:: python

    dataset = acq.get_dataset()
    img = dataset.read_image(time=0)  # returns a numpy array

For finished acquisitions, open the dataset from disk:

.. code-block:: python

    from pycromanager import Dataset
    dataset = Dataset('/path/to/data')

Individual images can be accessed using :meth:`read_image<pycromanager.Dataset.read_image>`:

.. code-block:: python

    img = dataset.read_image(z=0)
    img_metadata = dataset.read_metadata(z=0)


Opening Data as Dask Array
`````````````````````````````

For efficient handling of large datasets, open all data at once as a dask array. This can be used to open datasets that are too large to fit in memory, by only loading the data that is needed for a particular operation:

.. code-block:: python

    dask_array = dataset.as_array()

    # Perform operations like numpy arrays
    # For example, take max intenisty projection along axis 0
    max_intensity = np.max(dask_array[0, 0], axis=0)


You can also slice along particular axes:

.. code-block:: python

    dask_array = dataset.as_array(z=0, time=2)


Data Visualization
=============================

Pycro-Manager offers flexible options for visualizing while it is being acquired, described in :doc:`viewers`.

Datasets that have already been acquired can be visualized using napari:

.. code-block:: python

    dask_array = dataset.as_array()

    # Visualize data using napari
    import napari
    viewer = napari.Viewer()
    viewer.add_image(dask_array)
    napari.run()



.. toctree::
   :maxdepth: 1
   :hidden:

   viewers




Advanced Acquisition Features
=============================

Pycro-Manager offers a range of advanced features for customizing and extending the basic acquisition functionality, enabling complex experimental designs and specialized imaging techniques.


Customizing Acquisition Behavior
````````````````````````````````

Pycro-Manager offers several features to modify the acquisition process:

- :ref:`acq_events`: Define custom acquisition instructions.
- :ref:`acq_hooks`: Inject custom code at specific points in the acquisition process.
- :ref:`img_processors`: Modify or process image data on-the-fly.
- :doc:`image_saved_callbacks`: Execute custom code when images are saved.

The following figure illustrates how these features integrate into the acquisition process:

.. figure:: event_hook_processor_figure.png
   :width: 800
   :alt: Overview of Pycro-Manager's acquisition process

   **Pycro-Manager's acquisition process.** Blue: acquisition events from code or GUI. Green: hardware control thread for optimized instructions and image acquisition. Magenta: image saving and display. Acquisition events, hooks, and image processors enable customization throughout the process. Image saved callbacks (not shown) occur after saving and display.

.. toctree::
   :maxdepth: 1
   :hidden:

   acq_events
   acq_hooks
   img_processors
   image_saved_callbacks

Monitoring Progress with Notifications
```````````````````````````````````````

Receive real-time updates about the acquisition process with :doc:`notifications`, enabling better experiment tracking and debugging:

.. toctree::
   :maxdepth: 1
   :hidden:

   notifications


Adaptive Microscopy
```````````````````````````````

:doc:`adaptive_acq`: shows how to modify acquisition based on acquired data, allowing for dynamic and responsive experiments (also known as "smart microscopy").

.. toctree::
   :maxdepth: 1
   :hidden:

   adaptive_acq


Tiling Fields-of-View for large samples
````````````````````````````````````````

Pycro-Manager provides :ref:`special_acqs`

- :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>`: For imaging large samples across multiple fields of view.
- :class:`ExploreAcquisition<pycromanager.ExploreAcquisition>`: Interactive XY and Z navigation for sample exploration.
- :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>`: Advanced features for sample mapping and 3D datasets.


.. toctree::
   :maxdepth: 1
   :hidden:

   special_acqs


Hardware triggering
```````````````````````````````

:doc:`hardware_triggering`: describes how to use hardware synchronization to maximize acquisition speed and precision.

.. toctree::
   :maxdepth: 1
   :hidden:

   hardware_triggering

















