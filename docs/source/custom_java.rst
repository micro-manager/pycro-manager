
*****************************
Calling custom Java code
*****************************

You can also use the :class:`Bridge<pycromanager.Bridge>` to call your own Java code (such as a micro-manager Java plugin). The construction of an arbitrary Java object is show below using Micro-Magellan as an example:

.. code-block:: python

	magellan_api = bridge.construct_java_object('org.micromanager.magellan.api.MagellanAPI')

	#now call whatever Java methods the object has

If the constructor takes arguments, they can be passed in using:

.. code-block:: python

	java_obj = bridge.construct_java_object('the.full.classpath.to.TheClass', args=['demo', 30])


In either case, calling ``java_obj.`` and using IPython autocomplete to discover method names can be useful for development. Note that function names will be automatically translated from the camelCase Java convention to the Python convention of underscores between words (e.g. ``setExposure`` becomes ``set_exposure``)