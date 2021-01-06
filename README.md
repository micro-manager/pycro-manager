[![Documentation Status](https://readthedocs.org/projects/pycro-manager/badge/?version=latest)](https://pycro-manager.readthedocs.io/en/latest/?badge=latest)
[![License](https://img.shields.io/pypi/l/pycromanager.svg)](https://github.com/micro-manager/pycromanager/raw/master/LICENSE)
[![Python Version](https://img.shields.io/pypi/pyversions/pycromanager.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/pycromanager.svg)](https://pypi.org/project/pycromanager)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pycromanager.svg)](https://pypistats.org/packages/pycromanager)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
   
   
<img src="docs/source/pycromanager_banner.png" width="600">

`pycromanager` is a Python library for customized microscope hardware control and integration with image processing. It works together with [Micro-manager](https://micro-manager.org/) and [Micro-magellan](https://micro-manager.org/wiki/MicroMagellan).

Check out to the [pre-print](https://arxiv.org/abs/2006.11330) or the [documentation](https://pycro-manager.readthedocs.io/en/latest/) for an idea of the capabilities and how to get started.

Have a cool example of something you've done with `pycromanager` or an idea for improvement? Reach out on the issues page.

## Installing pycro-manager

1) Download the lastest version of [micro-manager 2.0](https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds)
2) Install pycro-manager using `pip install pycromanager`
3) Run Micro-Manager, select tools-options, and check the box that says Run server on port 4827 (you only need to do this once)

To verify everything is working, run the following code: 

```
from pycromanager import Bridge

bridge = Bridge()
print(bridge.get_core())
```
which will give an output like:

```
<pycromanager.core.mmcorej_CMMCore object at 0x7fe32824a208>
```

### Troubleshooting 

Upon creating the Bridge, you may see an error with something like:

```
UserWarning: Version mistmatch between Java ZMQ server and Python client.
Java ZMQ server version: 2.4.0
Python client expected version: 2.5.0
```

In this case case your Micro-manager version Pycro-manager versions are out of sync. Usually, this can be fixed by downloading the latest versions of both. Uprgade to the latest Pycro-manager with: 

```
pip install pycromanager --upgrade
```


## Contributing

We welcome community contributions to improve Pycro-manager, including bug fixes, improvements to documentation, examples of different use cases, or internal improvements. Check out the [contributing guide](https://github.com/micro-manager/pycro-manager/blob/master/Contributing.md) to see more about the workflow. Areas where community contributions would be especially helpful can be found on the [Issues](https://github.com/micro-manager/pycro-manager/issues) page with a **Help wanted** label

Information about how to setup a development environment for the Java parts of Pycro-manager can be found [here](https://github.com/micro-manager/pycro-manager/issues/123)
