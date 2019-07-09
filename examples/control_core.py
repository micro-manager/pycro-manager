from pygellan.acquire import MagellanBridge

#establish communication with Magellan
bridge = MagellanBridge()
#get object representing micro-manager core
core = bridge.get_core()


core.snapImage()
# ti = core.getTaggedImage()

# core.setSLMImage('SLM', 65539 * np.ones((1024), dtype=np.uint32))
# core.setProperty('Camera', 'CCDTemperature', 2)
# core.setROI(10, 12, 300, 200)
# core.getExposure()
# core.setAutoShutter(False)
# core.getImageWidth()
# core.getProperty('Camera', 'Exposure')

