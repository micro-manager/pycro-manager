# Pygellan
Pygellan is a Python library for enabling microscope acquisition control and data analysis. It works together with the [Micro-manager](https://micro-manager.org/) plugin, [Micro-magellan](https://micro-manager.org/wiki/MicroMagellan). Pygellan has two subpackages, `pygellan.acquire` and `pygellan.magellan_data` which are for data acquisition/hardware control and data anlysis, respectively. Pygellan is integrated with other projects in the scientific python ecosystem, including [Napari](https://github.com/napari/napari) (for data visualization) and [Dask](https://dask.org/) (for large scale data analysis). Pygellan development is currently in alpha--new features are being added and there are not yet guarantees on the stability of the API. Information about future development can be found on the issues page. Feel free to add comments, ideas, or other feedback on the [issues](https://github.com/henrypinkard/Pygellan/issues) page.

## Setup
1. Install pygellan using `pip install pygellan` (Pygellan is tested with Python 3.6 but should also work with other versions of Python3)

If using pygellan for acquisition control with micro-manager, you also must:

2. Download and install Nico Stuurman's 2.0gamma build of micro-manager. Latest nightly builds can be found [here](https://micro-manager.org/wiki/Version_2.0)

3. Open Micro-manager, select tools-options, and check the box that says "Run server on port 4827"


## Acquisition control
To use Pygellan for acqusition control, simply open the micro-manager2.0gamma GUI as usual and launch the Micro-magellan plugin. Start a python process in a way of your choosing (e.g. terminal, IDE, Jupyter notebook). Type:

````
from pygellan.acquire import PygellanBridge

bridge = PygellanBridge() #establish communication with Magellan
````
If the bridge object is created successfully, you are connected to Micro-Magellan and can use the rest of the `pygellan.acquire` API.

### Controlling the Micro-manager core
The micro-manager core provides low-level functionality like capturing images and controlling individual devices. An example can be seen [here](https://github.com/henrypinkard/Pygellan/blob/master/examples/micromanager_core.py).

The core API is discovered dynamically at runtime, though not every method is implemented. Typing `core.` and using autocomplete with IPython is the best way to discover which functions are available. Documentation on for the Java version of the core API (which Pygellan ultimately calls) can be found [here](https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmcorej/mmcorej/CMMCore.html).

### Controlling Micro-magellan acquisitions
*This area is still under active development*.  Future plans can be seen [on the issues tab](https://github.com/henrypinkard/Pygellan/issues) with the enhancement label. Comments/feedback./requests for different use cases are welcome.

In the mean time, some basic functionality is already available:

See [this example](https://github.com/henrypinkard/Pygellan/blob/master/examples/run_acquisition.py) for how to start and stop Micro-magellan acquisitions through Python.

[This example](https://github.com/henrypinkard/Pygellan/blob/master/examples/control_magellan_gui.py) shows how to call the various acquisition settings on the Micro-magellan GUI to automatically setup experiments

## Reading data in Python
The `pygellan.magellan_data` API enables reading of data acquired with pygellan/Micro-magellan directly in python. Tiles can be loaded individually, or all data can be loaded simulataneously into a memory-mapped [Dask](https://dask.org/) array, which works like a numpy array and also allows scalable processing of large datasets and viewing data in [Napari](https://github.com/napari/napari). More information can be seen in [this example](https://github.com/henrypinkard/Pygellan/blob/master/examples/read_and_visualize_magellan_data.py)
