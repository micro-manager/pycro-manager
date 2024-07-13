"""
Classes that wrap instance of known java objects for ease of use
"""
from pyjavaz import JavaObject, DEFAULT_BRIDGE_PORT, DEFAULT_BRIDGE_TIMEOUT
from mmpycorex.core import ZMQRemoteMMCoreJ # Don't delete this, its called by other code

class Magellan(JavaObject):
    """
    An instance of the Micro-Magellan API
    """

    def __new__(
        cls, convert_camel_case=True, port=DEFAULT_BRIDGE_PORT, timeout=DEFAULT_BRIDGE_TIMEOUT,
            new_socket=False, debug=False,
    ):
        """
        convert_camel_case : bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        debug: bool
            print debug messages
        """
        return JavaObject("org.micromanager.magellan.api.MagellanAPI", new_socket=new_socket,
                      port=port, timeout=timeout, convert_camel_case=convert_camel_case, debug=debug)


class Studio(JavaObject):
    """
    An instance of the Studio object that provides access to micro-manager Java APIs
    """

    def __new__(
        cls, convert_camel_case=True, port=DEFAULT_BRIDGE_PORT,
            timeout=DEFAULT_BRIDGE_TIMEOUT, new_socket=False, debug=False):
        """
        convert_camel_case : bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        debug: bool
            print debug messages
        """
        return JavaObject("org.micromanager.Studio", new_socket=new_socket,
                          port=port, timeout=timeout, convert_camel_case=convert_camel_case, debug=debug)

