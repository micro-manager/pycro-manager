"""
These classes wrap the ZMQ backend for ease of access
"""
from pycromanager.zmq_bridge._bridge import _JavaObjectShadow, _Bridge, _DataSocket
import zmq

DEFAULT_BRIDGE_PORT = _Bridge.DEFAULT_PORT
DEFAULT_BRIDGE_TIMEOUT = _Bridge.DEFAULT_TIMEOUT

class PullSocket(_DataSocket):
    """
    Create and connect to a pull socket on the given port
    """
    def __init__(
            self,
            port=_Bridge.DEFAULT_PORT,
            debug=False,
            ip_address="127.0.0.1"
    ):
        _DataSocket.__init__(self,
                             context=zmq.Context.instance(), port=port, type=zmq.PULL, debug=debug, ip_address=ip_address)


class PushSocket(_DataSocket):
    """
    Create and connect to a pull socket on the given port
    """
    def __init__(
            self,
            port=_Bridge.DEFAULT_PORT,
            debug=False,
            ip_address="127.0.0.1"
    ):
        _DataSocket.__init__(self,
                             context=zmq.Context.instance(), port=port, type=zmq.PUSH, debug=debug, ip_address=ip_address)



class JavaObject(_JavaObjectShadow):
    """
    Instance of a an object on the Java side. Returns a Python "Shadow" of the object, which behaves
        just like the object on the Java side (i.e. same methods, fields). Methods of the object can be inferred at
        runtime using iPython autocomplete
    """

    def __new__(
        cls,
        classpath,
        args: list = None,
        port=_Bridge.DEFAULT_PORT,
        timeout=_Bridge.DEFAULT_TIMEOUT,
        new_socket=False,
        convert_camel_case=True,
        debug=False,
    ):
        """
        classpath: str
            Full classpath of the java object
        args: list
            list of constructor arguments
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        convert_camel_case : bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        debug:
            print debug messages
        """
        bridge = _Bridge(port=port, timeout=timeout, convert_camel_case=convert_camel_case, debug=debug)
        return bridge._construct_java_object(classpath, new_socket=new_socket, args=args)


class JavaClass(_JavaObjectShadow):
    """
    Get an an object corresponding to a java class, for example to be used
        when calling static methods on the class directly
    """

    def __new__(
        cls,
        classpath,
        port=_Bridge.DEFAULT_PORT,
        timeout=_Bridge.DEFAULT_TIMEOUT,
        new_socket=False,
        convert_camel_case=True,
        debug=False,
    ):
        """
        classpath: str
            Full classpath of the java calss
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        convert_camel_case : bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        debug:
            print debug messages
        """
        bridge = _Bridge(port=port, timeout=timeout, convert_camel_case=convert_camel_case, debug=debug)
        return bridge._get_java_class(classpath, new_socket=new_socket)
