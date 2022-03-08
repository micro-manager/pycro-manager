"""
Classes that wrap instance of known java objects for ease of use
"""
from pycromanager.bridge import _JavaObjectShadow, Bridge
import threading

class _CoreCallback:
    """
    A class for recieving callbacks from the core, which are mostly used
    for the case where some hardware has changed
    See (https://github.com/micro-manager/mmCoreAndDevices/blob/main/MMCore/CoreCallback.cpp)

    """

    def __init__(self, callback_fn=None, bridge_port=Bridge.DEFAULT_PORT):
        self._closed = False
        self._thread = threading.Thread(
            target=self._callback_recieving_fn,
            name="CoreCallback",
            args=(bridge_port, self),
        )
        self.callback_fn = callback_fn
        self._thread.start()

    def _callback_recieving_fn(self, bridge_port, core_callback):
        callback_java = JavaObject(
            "org.micromanager.remote.RemoteCoreCallback", args=(Core(port=bridge_port),)
        )

        port = callback_java.get_push_port()
        pull_socket = Bridge._connect_pull(port)
        callback_java.start_push()

        while True:
            message = pull_socket.receive(timeout=100)
            if message is not None:
                core_callback._set_value(message)
            if core_callback._closed:
                callback_java.shutdown()
                break

    def _set_value(self, value):
        """
        Call the callback function
        :return:

        """
        function_name = value["name"]
        function_args = value["arguments"] if "arguments" in value else tuple()

        if self.callback_fn is not None:
            self.callback_fn(function_name, *function_args)

    def __del__(self):
        self._closed = True
        self._thread.join()


class Core(_JavaObjectShadow):
    """
    Remote instance of Micro-Manager Core
    """

    def __new__(
        cls, convert_camel_case=True, port=Bridge.DEFAULT_PORT, new_socket=False, debug=False, timeout=1000,
    ):
        """
        Parameters
        ----------
        convert_camel_case: bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        port: int
            The port of the Bridge used to create the object
        new_socket: bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges main port
        debug:
            print debug messages
        timeout:
            timeout for underlying bridge
        """
        bridge = Bridge(port=port, convert_camel_case=convert_camel_case, debug=debug, timeout=timeout)
        return bridge._construct_java_object("mmcorej.CMMCore", new_socket=new_socket)

    def get_core_callback(self, callback_fn=None, bridge_port=Bridge.DEFAULT_PORT):
        """
        Get a CoreCallback function that will fire callback_fn with (name, \*args) each
        time MMCore emits a callback signal

        callback_fn: Callable
            a function that takes (name, \*args)
        bridge_port: int
            port of the Core instance to get callbacks from
        """
        return _CoreCallback(callback_fn=callback_fn, bridge_port=bridge_port)


class Magellan(_JavaObjectShadow):
    """
    An instance of the Micro-Magellan API
    """

    def __new__(
        cls, convert_camel_case=True, port=Bridge.DEFAULT_PORT, new_socket=False, debug=False
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
        bridge = Bridge(port=port, convert_camel_case=True, debug=debug)
        return bridge._construct_java_object(
            "org.micromanager.magellan.api.MagellanAPI", new_socket=new_socket
        )


class Studio(_JavaObjectShadow):
    """
    An instance of the Studio object that provides access to micro-manager Java APIs
    """

    def __new__(
        cls, convert_camel_case=True, port=Bridge.DEFAULT_PORT, new_socket=False, debug=False
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
        bridge = Bridge(port=port, convert_camel_case=convert_camel_case, debug=debug)
        return bridge._construct_java_object("org.micromanager.Studio", new_socket=new_socket)


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
        port=Bridge.DEFAULT_PORT,
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
        bridge = Bridge(port=port, convert_camel_case=convert_camel_case, debug=debug)
        return bridge._construct_java_object(classpath, new_socket=new_socket, args=args)


class JavaClass(_JavaObjectShadow):
    """
    Get an an object corresponding to a java class, for example to be used
        when calling static methods on the class directly
    """

    def __new__(
        cls,
        classpath,
        port=Bridge.DEFAULT_PORT,
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
        bridge = Bridge(port=port, convert_camel_case=convert_camel_case, debug=debug)
        return bridge._get_java_class(classpath, new_socket=new_socket)
