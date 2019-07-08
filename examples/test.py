from pygellan.acquire import MagellanBridge

#establish communication with Magellan
bridge = MagellanBridge()
#get object representing micro-magellan API
magellan = bridge.get_magellan()

acquistions = magellan.getAcquisitions()
acq = acquistions[0]
acq.start()
# acq.abort()
acq.waitForCompletion()
pass

#Push pull socket

# socket = context.socket(zmq.PULL)
# socket.bind("tcp://127.0.0.1:{}".format(port))
#
# while True:
#     # socket.send(b"Hello")
#     #  Get the reply.
#     start = time.time()
#     message = socket.recv()
#     print(time.time() - start)
