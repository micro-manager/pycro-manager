# Pygellan
Pygellan is a Python library for enabling microscope acquisition control and data analysis. It works together with the [Micro-manager](https://micro-manager.org/) plugin, [Micro-magellan](https://micro-manager.org/wiki/MicroMagellan). Currently, the two main features of pygellan are hardware control/data acquisition and data reading.

## Setup
1. Install pygellan using `pip install pygellan` (Pygellan is tested with Python 3.6 but should also work with other versions of Python3)

2. (If using pygellan for acquisition control), download and install Nico Stuurman's 2.0gamma build of micro-manager. Latest nightly builds can be found [here](https://micro-manager.org/wiki/Version_2.0)

## Acquisition control
*Note: acquisition control APIs are still actively being developed. Feedback and suggestions are welcome on the issues tab of this repository.*

To use Pygellan for acqusition control, simply open the micro-manager2.0gamma GUI as usual and launch the Micro-magellan plugin. Start a python process in a way of your choosing (e.g. terminal, IDE, Jupyter notebook). Type:

````
from pygellan.acquire import MagellanBridge

bridge = MagellanBridge() #establish communication with Magellan
````
If the bridge object is created successfully, you are connected to Micro-Magellan and can use the rest of the `pygellan.acquire` API.

### Controlling the Micro-manager core
The micro-manager core provides low-level functionality like capturing images and controlling individual devices. An example can be seen [here](https://github.com/henrypinkard/Pygellan/blob/master/examples/micromanager_core.py).

The core API is discovered dynamically at runtime, though not every method is implemented. Typing `core.` and using autocomplete with IPython is the best way to discover which functions are available. Documentation on for the Java version of the core API (which Pygellan ultimately calls) can be found [here](https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html).

### Controlling Micro-magellan acquisitions
(*Under active development*)

See [this example](https://github.com/henrypinkard/Pygellan/blob/master/examples/run_acquisition.py) for how to start and stop Micro-magellan acquisitions through Python.

[This example](https://github.com/henrypinkard/Pygellan/blob/master/examples/control_magellan_gui.py) shows how to call the various acquisition settings on the Micro-magellan GUI to automatically setup experiments

## Reading data in Python
(Example coming soon...)
