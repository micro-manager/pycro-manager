"""
Classes that wrap instance of known java objects for ease of use
"""
from pycromanager.zmq import JavaObjectShadow, Bridge

class Core(JavaObjectShadow):

    def __new__(cls, convert_camel_case=True, port=Bridge.DEFAULT_PORT, new_port=False, debug=False):
        bridge = Bridge(port=port, convert_camel_case=True, debug=debug)
        return bridge.get_core()

    def __del__(self):
        print('deleting core')

class Dummy():

    def __del__(self):
        print('deleting')