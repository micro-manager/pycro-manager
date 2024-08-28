.. _acq_hooks:

****************************************************************
Acquisition hooks
****************************************************************


Acquisition hooks allow custom code to be injected at specific points in the acquisition process. This could be used, for example, to:

1. Execute arbitrary code during the acquisition cycle
2. Modify or delete acquisition events on-the-fly
3. Communicate with external devices for :ref:`hardware_triggering`

Types of Hooks
--------------

There are three types of hooks, each executed at a different point in the acquisition cycle:

1. ``pre_hardware_hook``: Executed before hardware updates
2. ``post_hardware_hook``: Executed after hardware updates, just before image capture
3. ``post_camera_hook``: Executed after the camera has been instructed to take images or wait for an external trigger


Basic Usage
-----------

The simplest hook is a function that takes a single argument (the current acquisition event):

.. code-block:: python

    def hook_fn(event):
        # Custom code here
        return event

    with Acquisition(directory='/path/to/saving/dir', name='acquisition_name',
                     post_hardware_hook_fn=hook_fn) as acq:
        # Acquisition code here


Modifying or Deleting Events
----------------------------

Hooks can modify or delete events by returning a modified event or not returning an event:

.. code-block:: python

    def hook_fn(event):
        if some_condition:
            return modified_event
        # Delete event by not returning anything

The effect of modifying or deleting events depends on the hook's position in the acquisition cycle. For example:

-  ``post_camera_hook_fn``: Modifications have no effect as hardware movement and camera activation have already occurred.
- ``pre_hardware_hook_fn``: Changes are fully applied. For example, modifying the z-position will cause the microscope to adjust its focus accordingly before image capture.
