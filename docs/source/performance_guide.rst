.. _performance_guide:

**************************
Performance Guide
**************************

Best programming practices for performance
================================================

With a proper hardware and software setup, pycromanager is capable of handling extremely large data volumes and rates (such as those seen in light sheet microscopy). The writer for the default format of pycromanager (`NDTiff <https://github.com/micro-manager/NDTiffStorage>`_), with multiple NVMe drives in a RAID configuration, has been clocked at sustaining multiple GB/s write speeds for hours at a time.

However, one performance limitation is the ~100 MB/s upper limit on data transfer over the Java-Python ``Bridge``. The current implementation of :ref:`img_processors` are bound by this limit, so if extremely fast data rates are needed, they should be avoided. One alternative is to use :ref:`image_saved_callbacks`, which do not pass image data over the ``Bridge``. Instead, after each image is written to disk, a small message is sent over the ``Bridge`` describing the location of the new data on disk. This can data can then be read natively in Python, without incurring the speed limits of the ``Bridge``.



.. _hardware_triggering:

Fast acquisition with hardware triggering
================================================

A standard acquisition is accomplished by sending commands from the computer to the devices each time a change (in, e.g., stage position or illumination) is required. This communication can add unnecessary latency (up to 100 ms) between image frames. Much faster and accurately timed operation is possible with most cameras (when acquiring a preset sequence of frames) as well as many other devices (when executing a pre-programmed sequence of commands).

For the fastest data acquisition speeds, routing TTL (Transistor-Transistor Logic) pulses over signal cables between hardware devices is essential. In such setups, hardware components are loaded with sequences of instructions (e.g. physical positions on a stage or a sequence of exposures on a camera). The hardware sequence can then be executed independently of the computer, while images are read off of the camera as fast as possible.

The :class:`Acquisition<pycromanager.Acquisition>` class has built in support for hardware sequencing, and it will automatically applied whenever it is supported by the hardware being used. There are two general synchronization strategies supported, which differ depending on what hardware device is the "leader" (i.e. the one sending out TTL pulses) and which one is the "follower" (i.e. the one receiving them).

In the default strategy, the camera is assumed to be the leader device. This means that it will run as fast as possible, and other peripheral devices synchronized with it should update their positions based on the TTL pulses outputed by the camera. Whenever the camera supports this behavior, there is little to no delay between successive frames, and any hardware that needs to repositioned also supports sequenceing, this behavior will automatically occur. If there is a need to adjust additional hardware settings in between successive sequences, this can done using :ref:`acq_hooks`.

In the second strategy, the camera is the "follower" device, and there is another external "leader" device which controls the synchronization between different hardware components. In this case, the camera should be placed into a mode where it will wait for external triggers before exposing. The specific properties that need to be set will differ from camera to camera, as this behavior is not currently a part of the micro-manager camera API. Once in this state, a pycro-manager :class:`Acquisition<pycromanager.Acquisition>` will cause the camera to shift into a state where it waits for a TTL pulse to trigger each exposure. The only thing remaining is to signal to the external leader device that the camera is ready, so that the leader device can begin its synchronization routine. This signalling can be done with an `post_camera_hook_fn` that runs after the camera has set into a ready state.


.. code-block:: python

    def hook_fn(event):
        ### start external leader device here ###
        return event

    # pass in the function as a post_hardware_hook
    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
                    post_camera_hook_fn=hook_fn) as acq:
            ### acquire some stuff ###





