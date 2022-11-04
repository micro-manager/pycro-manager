.. _img_processors:

**************************
Image processors
**************************

Image processors provide access to data as it is being acquired. This allows it to be modified, diverted to customized visualization and saving, or analyzed on-the-fly to control acquisition.

The simplest image processor function takes two arguments: the pixel data (a numpy array) and metadata (a python dictionary) of the current image. 

.. code-block:: python

    def img_process_fn(image, metadata):
		
        #add in some new metadata
        metadata['a_new_metadata_key'] = 'a new value'

        #modify the pixels by setting a 100 pixel square at the top left to 0
        image[:100, :100] = 0

        #propogate the image and metadata to the default viewer and saving classes
        return image, metadata

    # run an acquisition using this image processor
    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
    				image_process_fn=img_process_fn) as acq:
        ### acquire some stuff ###


One particularly useful metadata key is ``'Axes'`` which recovers the ``'axes'`` key that was in the **Acquisition event** in this image.

.. code-block:: python

    def img_process_fn(image, metadata):
        # get the time point index
        time_index = metadata['Axes']['time']


Returning multiple or zero images
====================================

Image processors are not required to take in one image and return one image. They can also return multiple images or no images. In the case of multiple images, they should be returned as a list of ``(image, metadata)`` tuples. The ``'Axes'`` or ``Channel`` metadata fields will need to be modified to uniquely identify the two images for the purposes of saving or the image viewer.

.. code-block:: python

    import copy

    def img_process_fn(image, metadata):
		
        # copy pixels in this example, but in reality
        # you might want to compute something different

        image_2 = np.array(image, copy=True)

        metadata_2 = copy.deepcopy(metadata)

        metadata_2['Channel'] = 'A_new_channel'

        #return as a list of tuples
        return [(image, metadata), (image2, md_2)]



Rather than returning one or more ``image, metadata`` tuples to propogate the image to the default viewer and saver, the image processing function can return nothing. This can be used if one wants to delete a specific image, or divert all images to customized saving/visualization code. If the latter behavior is desired, the :class:`Acquisition<pycromanager.Acquisition>` should be created without the ``name`` and ``directory`` fields.


.. code-block:: python

    def img_process_fn(image, metadata):

        ### send image and metadata somewhere ###

    # this acquisition won't show a viewer or save data
    with Acquisition(image_process_fn=img_process_fn) as acq:
        ### acquire some stuff ###


Adapting acquisition from image processors
============================================

In certain cases one may want to create addition **acquisition events** in response to one of the images. A three argument processing function can be used for this purpose. The third argument is the ``event_queue`` to which additional acquisition events can be added

.. code-block:: python

    def img_process_fn_events(image, metadata, event_queue):

        ### create a new acquisition event in response to something in the image ###
        # event =
        event_queue.put(event)

        return image, metadata

In the case of using feedback from the image to control acquisition, the typical syntax of ``with Acquisition...`` cannot be used because it will automatically close the acquisition too soon. Instead the acquisition should be created as:

.. code-block:: python

    acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
              image_process_fn=img_process_fn)

``acq.acquire`` will then need to be called at least once, so that there is an feedback loop between processed images and new events will be started.


When it is finished, it can be closed and cleaned up by passing an ``None`` to the ``event_queue``.

.. code-block:: python

    def img_process_fn_events(image, metadata, event_queue):

        if acq_end_condition:
            event_queue.put(None)
        else:
            #continue adding more events


Processing multiple images at once
====================================

In many cases, it is useful to process multiple images at a time, rather than just a single image. For example, this could be useful when processing should only occur after collecting a 3D volume at the end of a Z-stack. To accomplish
this, the function can hold onto a list of images until it contains a full Z-stack before processing.

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

	    return image, metadata

Performance
====================================
In the current implementation, image processors pass data back and forth through the Java-Python transport layer, which requires serializing and deserializing data to pass it from one process to another. This introduces a speed limitation of ~100 MB/s for image processors.

However, there is a potential workaround for this through the use of :ref:`image_saved_callbacks`. Here, rather than intercepting images after they are acquired, but before they are written to disk, the images are written to disk in Java code (which is very fast) without passing over the Java-Python Bridge, and as soon as they are written, a signal is sent across the Bridge that enables the data to be read off the disk. With fast enough hard drives, this can give access to acquired data significantly faster than image processors.


Applications
====================================

Image processors can be used to enable advanced applications, such as: 

-  :doc:`application_notebooks/Denoising acquired images using deep learning`
-  :doc:`application_notebooks/pycro_manager_tie_demo`
-  :doc:`application_notebooks/PSF_viewer`

