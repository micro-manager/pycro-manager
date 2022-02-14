.. _performance_guide:

**************************
Performance Guide
**************************


.. .. code-block:: python

..     def img_process_fn(image, metadata):
		
..         #add in some new metadata
..         metadata['a_new_metadata_key'] = 'a new value'

..         #modify the pixels by setting a 100 pixel square at the top left to 0
..         image[:100, :100] = 0

..         #propogate the image and metadata to the default viewer and saving classes
..         return image, metadata

..     # run an acquisition using this image processor
..     with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
..     				image_process_fn=img_process_fn) as acq:
..         ### acquire some stuff ###


.. One particularly useful metadata key is ``'Axes'`` which recovers the ``'axes'`` key that was in the **Acquisition event** in this image.

.. .. code-block:: python

..     def img_process_fn(image, metadata):
..         # get the time point index
..         time_index = metadata['Axes']['time']



