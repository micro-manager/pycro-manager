"""
This example shows how to use pygellan to call methods from a micromanager plugin using Micro-Magellan as an example

"""
from pygellan.acquire import PygellanBridge

bridge = PygellanBridge()

#use Pygellan to create a new instance of a class within the plugin
#in order for the class to be found, it must start with 'org.micromanager' and not contain the word 'internal' in its name
classpath = 'org.micromanager.magellan.api.MagellanAPI'
java_object = bridge.construct_java_object(classpath)
#now the java object is constructed, and you can call its methods to interact with other parts of the plugin through python
