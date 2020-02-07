"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge

bridge = PygellanBridge()
mm=bridge.get_studio()
mmc=bridge.get_core()

while True:
    mm.live().snap(True)

