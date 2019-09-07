from pygellan.acquire import MagellanBridge

#establish communication with Magellan
bridge = MagellanBridge()
#get object representing micro-magellan API
magellan = bridge.get_magellan()

#get this list of acquisitions in the magellan GUI
acquistions = magellan.get_acquisitions()
#grab the first acquisition in the list
acq = acquistions[0]
acq.start()

# block until the acquisition is complete
acq.wait_for_completion()
