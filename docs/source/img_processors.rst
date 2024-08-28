.. _img_processors:

**************************
Image processors
**************************

Image processors allow real-time access to acquired data for modification, custom visualization, saving, or on-the-fly analysis to control acquisition.


Basic Usage
-----------

A simple image processor function takes two arguments: ``image`` (numpy array) and ``metadata`` (python dictionary).

.. code-block:: python

    def img_process_fn(image, metadata):
        # Add new metadata
        metadata['new_key'] = 'new value'

        # Modify image
        image[:100, :100] = 0

        # propogate the image and metadata to the default viewer and saving classes
        return image, metadata

    # run an acquisition using this image processor
    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
                     image_process_fn=img_process_fn) as acq:
        # Acquisition code here

Tip: Access the the image's ``axes`` using ``metadata['Axes']``:

.. code-block:: python

    def img_process_fn(image, metadata):
        # get the time point index
        time_index = metadata['Axes']['time']


Advanced Features
-----------------

1. Returning multiple Images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Image processors can return multiple images by returning a list of ``(image, metadata)`` tuples. Be sure to modify the ``'Axes'`` metadata field to uniquely identify each image for saving or viewing. For example, this code shows how to split into a single image into two images in different channels:

.. code-block:: python

    def img_process_fn(image, metadata):
        image_2 = np.array(image, copy=True)
        metadata_2 = copy.deepcopy(metadata)
        metadata_2['Axes']['channel'] = 'New_channel'
        metadata['Axes']['channel'] = 'Old_channel'
        return [(image, metadata), (image_2, metadata_2)]



2. Custom Saving and Viewing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To implement custom saving or viewing, return nothing from the image processor. Create the :class:`Acquisition<pycromanager.Acquisition>` without ``name`` and ``directory`` fields:

.. code-block:: python

    def img_process_fn(image, metadata):
        # Custom saving or viewing logic here

    with Acquisition(image_process_fn=img_process_fn) as acq:
        # Acquisition code here


3. Processing multiple images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For operations on multiple images (e.g., Z-stacks), accumulate images until a complete set is available:

.. code-block:: python

	# The number of images per a full Z-stack
	num_z_steps = 10

	def img_process_fn(image, metadata):
	    # accumulate individual Z images
	    if not hasattr(img_process_fn, "images"):
	        img_process_fn.images = []
	    img_process_fn.images.append(image)

	    if len(img_process_fn.images) == num_z_steps:
	        # if last image in z stack, combine into a ZYX array
	        zyx_array = np.stack(img_process_fn.images, axis=0)

	        ### Do some processing on the 3D stack ###

        # This returns the original image and metadata, but in
        # this scenario, a possible alternative is to return nothing
        # until an entire Z-stack is processed
        return image, metadata



Adapting acquisition from image processors
-------------------------------------------

.. note::

    Adapting acquisition from image processors is an older feature. The newer :ref:`adaptive_acq` API is now the reccomended way to do this. However, the approach below still works.


To create additional :ref:`acq_events` based on acquired images, use a three-argument image processor:

.. code-block:: python

    def img_process_fn_events(image, metadata, event_queue):
        # Create a new acquisition event based on the image
        new_event = create_new_event(image, metadata)
        event_queue.put(new_event)
        return image, metadata



For adaptive acquisition, create the ``Acquisition`` object separately and call ``acquire`` manually:

.. code-block:: python

    acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
                      image_process_fn=img_process_fn_events)
    acq.acquire()  # Start the feedback loop

To end the acquisition, put ``None`` in the ``event_queue``:

.. code-block:: python

    def img_process_fn_events(image, metadata, event_queue):
        if acq_end_condition:
            event_queue.put(None)
        else:
            # Continue adding more events



Performance
------------

The performance of image processors is dependent on the backend used (see :ref:`backends`). When running micro-manager with the Java backend (either by opening the Micro-Manager application or launching Java backend headless mode), images are acquired in a separate Java process and must be passed to the Python process for processing. This transfer is limited to ~100 MB/s.

If speeds faster than this are required, consider using the :ref:`image_saved_callbacks` feature, which allows images to be saved to disk in Java code (which is can be much faster) and then read off the disk in Python. This can be significantly faster than using image processors.

Alternatively, if the Micro-Manager application is not required, consider using the python backend, in which images are acquired and processed in the same Python process, avoiding the Java-Python transport layer entirely.

: note:

    Users of the python backend may also be interested in `ExEngine <https://exengine.readthedocs.io/en/latest/>`_, a newer project which provides a more flexible and powerful module for doing the same things as pycro-manager does, and more.
