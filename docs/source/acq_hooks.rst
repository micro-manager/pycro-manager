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

Depending on where in the acquisition cycle the hook is, modifying or deleting the event may not have any effect. For example, modifying an event in a  ``post_camera_hook_fn`` won't have any effect since the hardware has already been moved and the camera started. In contrast, in a ``pre_hardware_hook_fn``, the event can be modified and the acquistion engine will use the modified event. For example, the z position could be changed in the hook function, which would cause the acquisition engine to move the microscope's focus drive to a different position than it otherwise woudl have prior to taking an image.

A hook function that takes two arguments can also be used in cases where one wants to submit additional acquisition events. The second argument, ``event_queue``, can be used for submitting additional acquisition events:

.. code-block:: python
	
	def hook_fn(event, event_queue):

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

    def hook_fn(event, event_queue):

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

