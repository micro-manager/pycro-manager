.. _setup:

********************
Installation/setup
********************


- Install pycro-manager using ``pip install pycromanager``

- Download newest version of `micro-manager 2.0 <https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds>`_

- Download and install Micro-Manager, either by downloding a nightly build from the `Micro-Manager website <https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds>`_, or programatically using the :ref:`installation api <download_install_api>` function:

    .. code-block:: python

        from mmpycorex import download_and_install_mm
        download_and_install_mm()

- Open Micro-Manager, select **tools-options**, and check the box that says **Run server on port 4827** (you only need to do this once)

Verify that installation worked
################################

Run the following code:

.. code-block:: python

	from pycromanager import Core

	core = Core()
	print(core)

which will give an output like:

.. code-block:: python

	<pycromanager.core.mmcorej_CMMCore object at 0x7fe32824a208>


