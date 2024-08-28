.. _adaptive_acq:

======================
Adaptive Acquisitions
======================


Pycro-Manager's ``Acquisition`` class allows the acquisition process to be modified based on acquired data. This enables dynamic, responsive experiments, also known as "smart microscopy".

This API is designed to provide both performance and easily understandable code. Parallelization is essential for many smart microscopy experiments, which require simultaneous hardware control, image acquisition, and data processing. However, the logic of an experiment is more easily understood as a sequence of decisions and actions. The API bridges this gap, enabling that looks like a single sequential script but takes advantage of parallelizing operations when possible.

Unlike simple acquisitions where all events are sent in a single ``Acquisition.submit(...)`` call, adaptive acquisitions require multiple ``submit`` calls. Events are submitted, they produce images, those images are analyzed, and based on this analysis, new events are created.

The key object in adaptive microscopy is the ``AcquisitionFuture``. Any time an event or events are submitted, an ``AcquisitionFuture`` is returned. The ``AcquisitionFuture`` can be used to access specific data as soon as it is ready.

This example shows an experiment which alternates between fast and slow time-lapses based on image analysis:

Example: Alternating Time-lapses
--------------------------------

.. code-block:: python

    from pycromanager import Acquisition, multi_d_acquisition_events

    def analyze_image(image):
        # Placeholder for image analysis
        return image.max() > threshold

    with Acquisition(directory='/path/to/save', name='adaptive_acq') as acq:
        for loop_index in range(10):  # Run 10 adaptive cycles
            # Acquire a single image
            event = {'axes': {'loop_index': loop_index}}
            future = acq.submit(event)

            # Wait for the image and analyze it
            image = future.await_image_saved(event['axes'])

            if analyze_image(image):
                # Fast time-lapse: 100 images, 1 second apart
                events = multi_d_acquisition_events(num_time_points=100, time_interval_s=1)
            else:
                # Slow time-lapse: 5 images, 20 seconds apart
                events = multi_d_acquisition_events(num_time_points=5, time_interval_s=20)

            # Add the loop index to the events so that successive timelapses have unique axes
            for event in events:
                event['axes']['loop_index'] = loop_index

            acq.submit(events)



Additional Features
-------------------

1. **Awaiting Multiple Images**

   The ``AcquisitionFuture`` can wait for multiple images simultaneously, only returning when all images are saved:

   .. code-block:: python

       future = acq.submit(events)
       images = future.await_image_saved([{'time': 2}, {'time': 3}, {'time': 4}])

   This is useful when analysis requires multiple images, such as 3D image processing on a Z-stack.


2. **Awaiting Specific Execution Milestones**

  Specific execution milestones can be awaited:

   .. code-block:: python

       from pycromanager import AcqNotification

       future = acq.submit(events)
       future.await_execution(milestone=AcqNotification.Hardware.POST_HARDWARE, axes={'time': 1})



For further information, see the :ref:`adaptive_acq_api` API
