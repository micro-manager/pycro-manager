.. _hardware_triggering:

********************************************
Fast acquisition with hardware triggering
********************************************

For the fastest acquisition data acquisition speeds, hardware triggering using TTL pulses is essential. In such setups, hardware components are loaded with sequences of instructions (e.g. physical positions on a stage or a sequence of exposures on a camera). The sequence can then be executed independently of the computer, except for frames being read off a camera as fast as possible.

The :class:`Acquisition<pycromanager.Acquisition>` class has built in support for hardware sequencing, and it will automatically applied whenever it is supported by the hardware being used. There are two general synchronization strategies supported, which differ depending on what hardware device is the "master" (i.e. the one sending out TTL pulses) and which one is the "slave" (i.e. the one receiving them).

In the default strategy, the camera is assumed to be the master device. This means that it will run as fast as possible, and other peripheral devices synchronized with it should update their positions based on the TTL pulses outputed by the camera. Whenever the camera supports this behavior, there is little to no delay between successive frames, and any hardware that needs to repositioned also supports sequenceing, this behavior will automatically occur. If there is a need to adjust additional hardware settings in between successive sequences, this can done using :ref:`acq_hooks`.

In the second strategy, the camera is the "slave" device, and there is another external "master" device which controls the synchronization between different hardware components. In this case, the camera should be placed into a mode where it will wait for external triggers before exposing. The specific properties that need to be set will differ from camera to camera, as this behavior is not currently a part of the micro-manager camera API. Once in this state, a pycro-manager :class:`Acquisition<pycromanager.Acquisition>` will cause the camera to shift into a state where it waits for a TTL pulse to trigger each exposure. The only thing remaining is to signal to the external master device that the camera is ready, and so the master device can now begin its synchronization routine. This signalling can be done with an acquisition hook that runs after the camera has been started.


.. code-block:: python

	def hook_fn(event):
		### start external master device here ###
		return event

	# pass in the function as a post_hardware_hook
	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
					post_camera_hook_fn=hook_fn) as acq:
			### acquire some stuff ###






