"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge
bridge=PygellanBridge()
mm=bridge.get_studio()

d = mm.data()
store = d.create_ram_datastore()
disp = mm.displays()
disp.create_display(store)
pass