"""
This example shows how to use pygellan to interact with the micro-manager java API (a.k.a. the "studio")
"""
from pygellan.acquire import PygellanBridge
bridge=PygellanBridge()
mm=bridge.get_studio()
mmc=bridge.get_core()
mm.live().snap(True)
dv=mm.displays()
av=dv.get_active_data_viewer()
dp=av.get_data_provider()
img=dp.get_any_image()
img.get_height()
img.get_metadata()
md=img.get_metadata()
md.get_camera()

image = img.get_raw_pixels_copy()
pass