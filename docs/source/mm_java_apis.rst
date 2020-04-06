**********************************
Micro-manager Java APIs
**********************************

``pycromanager`` provides a simple way to control the Java/Beanshell APIs of micromanager through Python. In some cases it may be run existing `beanshell scripts <https://micro-manager.org/wiki/Example_Beanshell_scripts>`_ with little to no modifcation. The full Java documentation for this API can be found `here <https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmstudio/org/micromanager/Studio.html>`_. Setting the ``convert_camel_case`` option to ``False`` here may be especially useful, because it keeps the function names in the Java convention of ``camelCaseCapitalization`` rather than automatically converting to the Python convention of ``names_with_underscores``.



.. code-block:: python

	from pycromanager import Bridge
	
	bridge = Bridge(convert_camel_case=False)

	#get the micro-manager studio object:
	studio = bridge.get_studio()

	#now use the studio for something