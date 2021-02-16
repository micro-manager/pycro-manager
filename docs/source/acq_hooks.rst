.. _acq_hooks:

****************************************************************
Acquisition hooks
****************************************************************

Acquisition hooks can be used for several purposes: 1) Executing arbitrary code at different points within the acquisition cycle. For example, this could be used to incorporate devices outside of micro-manager into the acquisition cycle. 2) Modifying/deleting acquisition events in progress, for example to skip certain channels, or applying focus corrections on-the-fly. 3) Communcation with external devices at specific points in the acquisition cycle to enable the use of hardware TTL triggering for fast acquisitions

Hooks can either be executed before the hardware updates for a particular acquisition event (a ``pre_hardware_hook``), just after the hardware updates, just before the image is captured (a ``post_hardware_hook``), or after the camera has been instructed to take images or wait for an external trigger (a ``post_camera_hook``). 

The simplest type of acquisition hook is function that takes a single argument (the current acquisition event). Pass this function to the acquisition by adding it as an argument in the constructor. This form might be used, for example, to control other hardware and have it synchronized with acquisition.

.. code-block:: python

	def hook_fn(event):
		### Do some other stuff here ###
		return event

	# pass in the function as a post_hardware_hook
	with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
    				post_hardware_hook_fn=hook_fn) as acq:
    		### acquire some stuff ###


Acquisition hooks can also be used to modify or delete acquisition events:

.. code-block:: python

  def hook_fn(event):
	if some_condition:
		return event
	# condition isn't met, so delete this event by not returning it


A hook function that takes three arguments can also be used in cases where one wants to submit additional acquisition events or interact with classes on the Java side (such as the micro-manager core) through the :class:`Bridge<pycromanager.Bridge>`.

.. code-block:: python
	
	def hook_fn(event, bridge, event_queue):
		core = bridge.get_core()

		### now call some functions in the micro-manager core ###

		return event

The third argument, ``event_queue``, can be used for submitting additional acquisition events:


.. code-block:: python
	
	#this hook function can control the micro-manager core
	def hook_fn(event, bridge, event_queue):

		### create a new acquisition event in response to something ###
		#event =
		event_queue.put(event)

		return event


If additional events will be submitted here, the typical syntax of ``with Acquisition...`` cannot be used because it will automatically close the acquisition too soon. Instead the acquisition should be created as:

.. code-block:: python

	acq = Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
    				post_hardware_hook_fn=hook_fn)

When it is finished, it can be closed and cleaned up by passing an ``None`` to the ``event_queue``.

.. code-block:: python
	
	#this hook function can control the micro-manager core
	def hook_fn(event, bridge, event_queue):

		if acq_end_condition:
			event_queue.put(None)
		else:
			return event


Applications
====================================
	
Acquisition hooks can be used to enable advanced applications, such as: 

-  :doc:`application_notebooks/Single_shot_autofocus_pycromanager`
-  :doc:`application_notebooks/external_master_tutorial`
-  :doc:`application_notebooks/Learned_adaptive_multiphoton_illumination`

