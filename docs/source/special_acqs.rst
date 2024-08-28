.. _special_acqs:

****************************************************************
Acquisitions for XY Tiling Multiple Fields-of-View
****************************************************************



Pycro-Manager supports specialized Acquisition types for specific applications. The current special types are all for imaging large samples by capturing multiple fields of view and stitching them together. These include:

1. :class:`XYTiledAcquisition<pycromanager.XYTiledAcquisition>`
   - Images large samples by capturing multiple fields of view
   - Stitches images into a single contiguous image
   - Uses a multi-resolution file format for efficient visualization at multiple scales

2. :class:`ExploreAcquisition<pycromanager.ExploreAcquisition>`
   - Extends XYTiledAcquisition
   - Provides a user interface for XY and Z stage navigation
   - Allows interactive selection of imaging locations

3. :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>`
   - Controls the `Micro-Magellan <https://micro-manager.org/wiki/MicroMagellan>`_ plugin
   - Offers sample mapping, region of interest definition, and specialized 3D dataset collection

Stitching acquired images
--------------------------

For these acquisitions the images are acquired in a grid pattern and then stitched together. The stitching can be done automatically by setting the ``stitched`` argument to ``True`` in the ``as_array`` method. This will return a Dask array that is a single contiguous image, and doesn't pull individual tiles into memory until they are needed. This is useful for large images that don't fit in memory.

.. code-block:: python

    dask_array = dataset.as_array(stitched=True)








.. _xy_tiled_acq:

XYTiled Acquisition
-------------------

XYTiled Acquisitions support imaging of large samples by tiling multiple images together. Data is saved in a multi-resolution pyramid for efficient viewing at different zoom levels.

.. note::

   This functionality requires a correctly calibrated affine transform matrix in the current configuration. Calibrate using the pixel size calibrator in Micro-Manager (``Devices``--``Pixel Size Calibration``).

Different XY fields of view can be acquired adding ``row`` and ``column`` indices in the ``axes`` of the acquisition event.

Usage:

.. code-block:: python

    from pycromanager import XYTiledAcquisition

    with XYTiledAcquisition(directory='/path/to/saving/dir', name='saving_name', tile_overlap=10) as acq:
        # 10 pixel overlap between adjacent tiles

        # Acquire a 2 x 1 grid
        acq.acquire({'axes': {'row': 0, 'col': 0}})
        acq.acquire({'axes': {'row': 1, 'col': 0}})




Explore Acquisitions
--------------------

Explore Acquisitions extend XYTiled Acquisitions with a graphical interface for user-controlled image acquisition:

.. image:: explore.gif
   :width: 800
   :alt: Explore acquisition


.. _magellan_acq_launch:

Micro-Magellan Acquisition
===============================
Another alternative is to launch `Micro-magellan <https://micro-manager.org/wiki/MicroMagellan>`_ acquisitions. These include both regular and `explore acquisitions <https://micro-manager.org/wiki/MicroMagellan#Explore_Acquisitions>`_.

Micro-Magellan acquisitions can be run using the :class:`MagellanAcquisition<pycromanager.MagellanAcquisition>` class. The class requires as an argument either ``magellan_acq_index`` or ``magellan_explore``. The former corresponds to the position of the acquisition to be launched in the **Acquisition(s)** section of the Micro-Magellan GUI. Passing in 0 corresponds to the default acquisition. Greater numbers can be used to programatically control multiple acquisitions. The latter corresponds to explore acquisitions, which can be launched by setting the ``magellan_explore`` argument equal to ``True``.


.. code-block:: python

	from pycromanager import MagellanAcquisition

	# no need to use the normal "with" syntax because these acquisition are cleaned up automatically
	acq = MagellanAcquisition(magellan_acq_index=0)

	# Or do this to launch an explore acquisition
	acq = MagellanAcquisition(magellan_explore=True)

	# Optional: block here until the acquisition is finished
	acq.await_completion()

Like the other mechanisms for running acquisitions, Micro-Magellan acquisitions can be used with :ref:`acq_hooks` and :ref:`img_processors`.

