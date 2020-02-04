from pygellan.acquire import PygellanBridge

#establish communication with Magellan
bridge = PygellanBridge()
#get object representing micro-magellan API
magellan = bridge.get_magellan()

#get this list of acquisitions in the magellan GUI
acquistions = magellan.get_acquisitions()
#grab the first acquisition in the list (There is always one created by default)
acq = acquistions[0]
#alternatively, a new acquisition can be created
acq2 = magellan.create_acquisition()

acq2.start()

# block until the acquisition is complete
acq.wait_for_completion()
