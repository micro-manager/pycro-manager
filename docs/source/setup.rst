********************
Installation/setup
********************


- Install pycro-manager using ``pip install pycromanager``

- Download newest version of `micro-manager 2.0 <https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds>`_

- Open Micro-Manager, select tools-options, and check the box that says **Run server on port 4827** (you only need to do this once)

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


################################
Troubleshooting
################################

Upon creating the Bridge, you may see an error with something like:

.. code-block:: none

	UserWarning: Version mistmatch between Java ZMQ server and Python client. 
	Java ZMQ server version: 2.4.0
	Python client expected version: 2.5.0

In this case case your Micro-manager version Pycro-manager versions are out of sync. The best fix is to down the latest versions of both. Uprgade to the latest Pycro-manager with: ``pip install pycromanager --upgrade``