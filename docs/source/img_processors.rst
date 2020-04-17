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
		#get the time point index
		time_index = metadata['Axes']['time']


As an alternative to returning ``image, metadata`` to propogate the image to the default viewer and saver, the image processing function can not return anything. This can be used if one wants to delete a specific image, or divert all images to customized saving/visualization code. If the latter behavior is desired, the :class:`Acquisition<pycromanager.Acquisition>` should be created without the ``name`` and ``directory`` fields.


.. code-block:: python

	def img_process_fn(image, metadata):
		
		### send iamge and metadata somewhere ###

	# this acquisition won't show a viewer or save data
	with Acquisition(image_process_fn=img_process_fn) as acq:
    		### acquire some stuff ###


In certain cases one may want to either control something on the Java side or create addition **acquisition events** in response to one of the images. A four argument processing function can be used for this purpose. This gives access to the :class:`Bridge<pycromanager.Bridge>` for interacting with the Java side, and an ``event_queue`` to which additional acquisition events can be added

.. code-block:: python

	def img_process_fn_events(image, metadata, bridge, event_queue):
		
		### create a new acquisition event in response to something in the image ###
		#event =
		event_queue.put(event)
		
		return image, metadata

In the case of using feedback from the image to control acquisition, the typical syntax of ``with Acquisition...`` cannot be used because it will automatically close the acquisition too soon. Instead the acquisition should be created as:

.. code-block:: python

	acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
    				image_process_fn=img_process_fn)

When it is finished, it can be closed and cleaned up by passing an ``None`` to the ``event_queue``.

.. code-block:: python

	def img_process_fn_events(image, metadata, bridge, event_queue):
		
		if acq_end_condition:
			event_queue.put(None)
		else:
			#continue adding more events
	



TODO: add mode to return multiple images so that additional images can be inserted

