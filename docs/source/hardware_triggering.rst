.. _hardware_triggering:

Hardware Triggering and Sequencing
==================================

Hardware triggering and sequencing are crucial for achieving fast, precisely synchronized image acquisition by minimizing computer-hardware communication. This approach can significantly reduce latency between image frames.

How It Works
------------

In hardware-triggered setups:

1. Hardware components are pre-loaded with sequences of instructions (e.g., stage positions or digital outputs to control lasers).
2. The sequence is executed independently of the computer.
3. TTL (Transistor-Transistor Logic) pulses are routed between devices for synchronization.
4. Images are read from the camera as quickly as possible.

Automatic Hardware Sequencing
-----------------------------

The :class:`Acquisition<pycromanager.Acquisition>` class automatically applies hardware sequencing when:

1. No delays are requested between successive images.
2. All hardware position changes support instruction sequencing.
3. All events are submitted to ``acq.acquire()`` in a single call.

Synchronization Strategies
--------------------------

Pycro-Manager supports two general synchronization strategies:

1. Camera as Leader (Default):
   - The camera runs at maximum speed.
   - Other devices update based on TTL pulses from the camera.


2. External Device as Leader:
   - An external device timing device controls synchronization.
   - The camera is set to wait for external triggers.
   - Use a ``post_camera_hook_fn`` to signal the external leader device to start:

   .. code-block:: python

       def hook_fn(event):
           # Start external leader device here
           return event

       with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
                        post_camera_hook_fn=hook_fn) as acq:
           # Acquisition code here

Using Acquisition Hooks with Hardware Sequencing
------------------------------------------------

When hardware sequencing is engaged:
- The ``event`` passed to hooks will be a ``list`` of ``dict`` objects (a sequence of events).
- Hooks are called once for the whole sequence, not for each event.

Disabling Hardware Sequencing
-----------------------------

To disable hardware sequencing, submit events one at a time:

.. code-block:: python

    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name') as acq:
        events = multi_d_acquisition_events(num_time_points=10)
        for event in events:
            acq.acquire(event)

Practical Example: Light-Sheet Microscopy
--------------------------------------------

This `notebook <external_hardware_triggering_tutorial.ipynb>`_ shows an example of how to setup Pycro-Manager to run a microscope that utilizes an external controller as the leader device. Specifically, this tutorial controls a light-sheet microscope where a sample with fluorescent labels is scanned at a constant speed through an oblique light sheet. The stage controller provides the TTL signals that ensure the camera is synchronized to the scanning stage. This approach makes use of ``post_hardware`` and ``post_camera`` hook functions built into Pycro-Manager. Using these hook functions, it is possible to rapidly build and acquire a multiple terabyte acquisition consisting of millions of images.

.. toctree::
   :maxdepth: 1
   :hidden:

   external_hardware_triggering_tutorial.ipynb
