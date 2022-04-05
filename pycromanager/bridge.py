import json
import re
import time
import typing
import warnings
import inspect
import numpy as np
import zmq
import copy
import sys
from threading import Lock, local
import threading
from warnings import warn
import weakref

class DataSocket:
    """
    Wrapper for ZMQ socket that sends and recieves dictionaries
    Includes ZMQ client, push, and pull sockets
    """

    def __init__(self, context, port, type, debug=False, ip_address="127.0.0.1"):
        # request reply socket
        self._socket = context.socket(type)
        self._debug = debug
        # store these as wekrefs so that circular refs dont prevent garbage collection
        self._java_objects = weakref.WeakSet()
        self._port = port
        self._close_lock = Lock()
        self._closed = False
        if type == zmq.PUSH:
            if debug:
                print("binding {}".format(port))
            self._socket.bind("tcp://{}:{}".format(ip_address, port))
        else:
            if debug:
                print("connecting {}".format(port))
            self._socket.connect("tcp://{}:{}".format(ip_address, port))

    def _register_java_object(self, object):
        self._java_objects.add(object)

    def _convert_np_to_python(self, d):
        """
        recursively search dictionary and convert any values from numpy floats/ints to
        python floats/ints so they can be json serialized
        :return:
        """
        if type(d) != dict:
            return
        for k, v in d.items():
            if isinstance(v, dict):
                self._convert_np_to_python(v)
            elif type(v) == list:
                for e in v:
                    self._convert_np_to_python(e)
            elif np.issubdtype(type(v), np.floating):
                d[k] = float(v)
            elif np.issubdtype(type(v), np.integer):
                d[k] = int(v)

    def _make_array_identifier(self, entry):
        """
        make a string to replace bytes data or numpy array in message, which encode data type if numpy
        """
        # make up a random 32 bit int as the identifier
        # TODO: change to simple counting
        identifier = np.random.randint(-(2 ** 31), 2 ** 31 - 1, 1, dtype=np.int32)[0]
        # '@{some_number}_{bytes_per_pixel}'
        # if its a numpy array, include bytes per pixel, otherwise just interpret it as raw byts
        # TODO : I thinkg its always raw binary and the argument deserialization types handles conversion to java arrays
        # This definitely could use some cleanup and simplification. Probably best to encode the data type here and remove
        # argument deserialization types
        return identifier, "@" + str(int(identifier)) + "_" + str(
            0 if isinstance(entry, bytes) else entry.dtype.itemsize
        )

    def _remove_bytes(self, bytes_data, structure):
        if isinstance(structure, list):
            for i, entry in enumerate(structure):
                if isinstance(entry, bytes) or isinstance(entry, np.ndarray):
                    int_id, str_id = self._make_array_identifier(entry)
                    structure[i] = str_id
                    bytes_data.append((int_id, entry))
                elif isinstance(entry, list) or isinstance(entry, dict):
                    self._remove_bytes(bytes_data, entry)
        elif isinstance(structure, dict):
            for key in structure.keys():
                entry = structure[key]
                if isinstance(entry, bytes) or isinstance(entry, np.ndarray):
                    int_id, str_id = self._make_array_identifier(entry)
                    structure[key] = str_id
                    bytes_data.append((int_id, entry))
                elif isinstance(entry, list) or isinstance(entry, dict):
                    self._remove_bytes(bytes_data, structure[key])

    def send(self, message, timeout=0):
        if message is None:
            message = {}
        # make sure any np types convert to python types so they can be json serialized
        self._convert_np_to_python(message)
        # Send binary data in seperate messages so it doesnt need to be json serialized
        bytes_data = []
        self._remove_bytes(bytes_data, message)
        message_string = json.dumps(message)
        if self._debug:
            print("DEBUG, sending: {}".format(message))
        # convert keys to byte array
        key_vals = [(identifier.tobytes(), value) for identifier, value in bytes_data]
        message_parts = [bytes(message_string, "iso-8859-1")] + [
            item for keyval in key_vals for item in keyval
        ]
        if timeout == 0:
            self._socket.send_multipart(message_parts)
        else:
            start = time.time()
            while 1000 * (time.time() - start) < timeout:
                try:
                    self._socket.send_multipart(message_parts, flags=zmq.NOBLOCK)
                    return True
                except zmq.ZMQError:
                    pass  # ignore, keep trying
            return False

    def _replace_bytes(self, dict_or_list, hash, value):
        """
        Replace placeholders for byte arrays in JSON message with their actual values
        """
        if isinstance(dict_or_list, dict):
            for key in dict_or_list:
                if isinstance(dict_or_list[key], str) and "@" in dict_or_list[key]:
                    hash_in_message = int(
                        dict_or_list[key].split("@")[1], 16
                    )  # interpret hex hash string
                    if hash == hash_in_message:
                        dict_or_list[key] = value
                        return
                elif isinstance(dict_or_list[key], list) or isinstance(dict_or_list[key], dict):
                    self._replace_bytes(dict_or_list[key], hash, value)
        elif isinstance(dict_or_list, list):
            for i, entry in enumerate(dict_or_list):
                if isinstance(entry, str) and "@" in dict_or_list[entry]:
                    hash_in_message = int(entry.split("@")[1], 16)  # interpret hex hash string
                    if hash == hash_in_message:
                        dict_or_list[i] = value
                        return
                elif isinstance(entry, list) or isinstance(entry, dict):
                    self._replace_bytes(entry, hash, value)

    def receive(self, timeout=0):
        if timeout == 0:
            reply = self._socket.recv_multipart()
        else:
            start = time.time()
            reply = None
            while 1000 * (time.time() - start) < timeout:
                try:
                    reply = self._socket.recv_multipart(flags=zmq.NOBLOCK)
                    if reply is not None:
                        break
                except zmq.ZMQError:
                    pass  # ignore, keep trying
            if reply is None:
                return reply
        message = json.loads(reply[0].decode("iso-8859-1"))
        # replace any byte data placeholders with the byte data itself
        for i in np.arange(1, len(reply), 2):
            # messages come in pairs: first is hash, second it byte data
            identity_hash = int.from_bytes(reply[i], byteorder=sys.byteorder)
            value = reply[i + 1]
            self._replace_bytes(message, identity_hash, value)

        if self._debug:
            print("DEBUG, recieved: {}".format(message))
        self._check_exception(message)
        return message

    def _check_exception(self, response):
        if "type" in response and response["type"] == "exception":
            raise Exception(response["value"])

    def __del__(self):
        self.close() # make sure it closes properly

    def close(self):
        with self._close_lock:
            if not self._closed:
                for java_object in self._java_objects:
                    java_object._close()
                    del java_object #potentially redundant, trying to fix closing race condition
                self._java_objects = None
                self._socket.close()
                while not self._socket.closed:
                    time.sleep(0.01)
                self._socket = None
                if self._debug:
                    print('closed socket {}'.format(self._port))
                self._closed = True


class Bridge:
    """
    Create an object which acts as a client to a corresponding server (running in a Java process).
    This enables construction and interaction with arbitrary java objects. Each bridge object should
    be run using a context manager (i.e. `with Bridge() as b:`) or bridge.close() should be explicitly
    called when finished
    """

    DEFAULT_PORT = 4827
    DEFAULT_TIMEOUT = 500
    _EXPECTED_ZMQ_SERVER_VERSION = "4.2.0"

    def __new__(cls, timeout: int=DEFAULT_TIMEOUT, convert_camel_case: bool=True,  *args, **kwargs):
        """
        Only one instance of Bridge per a thread/port combo
        """
        port = kwargs.get('port', Bridge.DEFAULT_PORT)
        if not hasattr(Bridge, 'local'):
            Bridge.local = threading.local()
        if not hasattr(Bridge.local, 'bridges'):
            Bridge.local.bridges = {}
        if port not in Bridge.local.bridges.keys():
            Bridge.local.bridges[port] = []
            return super(Bridge, cls).__new__(cls)

        # clear old old refs that have been GCed
        remaining = []
        for i in range(len(Bridge.local.bridges[port])):
            if Bridge.local.bridges[port][i]() is not None:
                remaining.append(Bridge.local.bridges[port][i])
        Bridge.local.bridges[port] = remaining
        if len(Bridge.local.bridges[port]) == 0:
            return super(Bridge, cls).__new__(cls)
            
        return Bridge.local.bridges[port][0]()


    def __init__(
        self, port: int=DEFAULT_PORT, convert_camel_case: bool=True,
            debug: bool=False, ip_address: str="127.0.0.1", timeout: int=DEFAULT_TIMEOUT, iterate: bool = False
    ):
        """
        Parameters
        ----------
        port : int
            The port on which the bridge operates
        convert_camel_case : bool
            If True, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        debug : bool
            If True print helpful stuff for debugging
        iterate : bool
            If True, ListArray will be iterated and give lists
        """
        self._weak_self_ref = weakref.ref(self)
        Bridge.local.bridges[port].append(self._weak_self_ref)
        if hasattr(self, '_ip_address'):
            return #already initialized
        self._ip_address = ip_address
        self._port = port
        self._convert_camel_case = convert_camel_case
        self._debug = debug
        self._timeout = timeout
        self._iterate = iterate
        self._main_socket = DataSocket(
            zmq.Context.instance(), port, zmq.REQ, debug=debug, ip_address=self._ip_address
        )
        self._main_socket.send({"command": "connect", "debug": debug})
        self._class_factory = _JavaClassFactory()
        reply_json = self._main_socket.receive(timeout=timeout)
        if reply_json is None:
            raise TimeoutError(
                f"Socket timed out after {timeout} milliseconds. Is Micro-Manager running and is the ZMQ server on {port} option enabled?"
            )
        if reply_json["type"] == "exception":
            raise Exception(reply_json["message"])
        if "version" not in reply_json:
            reply_json["version"] = "2.0.0"  # before version was added
        if reply_json["version"] != self._EXPECTED_ZMQ_SERVER_VERSION:
            warnings.warn(
                "Version mistmatch between Java ZMQ server and Python client. "
                "\nJava ZMQ server version: {}\nPython client expected version: {}"
                "\n To fix, update to BOTH latest pycromanager and latest micro-manager nightly build".format(
                    reply_json["version"], self._EXPECTED_ZMQ_SERVER_VERSION
                )
            )


    def __enter__(self):
        warn('\nThe Bridge context manager (i.e. with Bridge...) is deprecated and will be \n'
             'removed in a future version. Bridge does not need to be explicitly created anymore.  \n'
             'Instead use the classes JavaObject, JavaClass, Core, Studio, Magellan', DeprecationWarning, stacklevel=2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _deserialize_object(self, serialized_object) -> typing.Type["_JavaObjectShadow"]:
        return self._class_factory.create(
            serialized_object, convert_camel_case=self._convert_camel_case
        )

    def _construct_java_object(self, classpath: str, new_socket: bool=False, args: list=None):
        """
        Create a new instance of a an object on the Java side. Returns a Python "Shadow" of the object, which behaves
        just like the object on the Java side (i.e. same methods, fields). Methods of the object can be inferred at
        runtime using iPython autocomplete

        Parameters
        ----------
        classpath : str
            Full classpath of the java object
        new_socket : bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges master port
        args : list
            list of arguments to the constructor, if applicable
        Returns
        -------

        Python  "Shadow" to the Java object
        """
        if args is None:
            args = []
        # classpath_minus_class = '.'.join(classpath.split('.')[:-1])
        # query the server for constructors matching this classpath
        message = {"command": "get-constructors", "classpath": classpath}
        self._main_socket.send(message)
        constructors = self._main_socket.receive()["api"]

        methods_with_name = [m for m in constructors if m["name"] == classpath]
        if len(methods_with_name) == 0:
            raise Exception("No valid java constructor found with classpath {}".format(classpath))
        valid_method_spec, deserialize_types = _check_method_args(methods_with_name, args)

        # Calling a constructor, rather than getting return from method
        message = {
            "command": "constructor",
            "classpath": classpath,
            "argument-types": valid_method_spec["arguments"],
            "argument-deserialization-types": deserialize_types,
            "arguments": _package_arguments(valid_method_spec, args),
        }
        if new_socket:
            message["new-port"] = True
        self._main_socket.send(message)
        serialized_object = self._main_socket.receive()
        if new_socket:
            socket = DataSocket(
                zmq.Context.instance(), serialized_object["port"], zmq.REQ, ip_address=self._ip_address
            )
        else:
            socket = self._main_socket
        return self._deserialize_object(serialized_object)(socket=socket,
                                                           serialized_object=serialized_object, bridge=self)

    def _get_java_class(self, classpath: str, new_socket: bool=False):
        """
        Get an an object corresponding to a java class, for example to be used
        when calling static methods on the class directly

        Parameters
        ----------
        classpath : str
            Full classpath of the java object
        new_socket : bool
            If True, will create new java object on a new port so that blocking calls will not interfere
            with the bridges master port
        Returns
        -------

        Python  "Shadow" to the Java class
        """
        message = {"command": "get-class", "classpath": classpath}
        if new_socket:
            message["new-port"] = True
        self._main_socket.send(message)
        serialized_object = self._main_socket.receive()

        if new_socket:
            socket = DataSocket(
                zmq.Context.instance(), serialized_object["port"], zmq.REQ, ip_address=self._ip_address
            )
        else:
            socket = self._main_socket
        return self._class_factory.create(
            serialized_object, convert_camel_case=self._convert_camel_case
        )(socket=socket, serialized_object=serialized_object, bridge=self)

    def _connect_push(self, port):
        """
        Connect a push socket on the given port
        :param port:
        :return:
        """
        return DataSocket(
            zmq.Context.instance(), port, zmq.PUSH, debug=self._debug, ip_address=self._ip_address
        )

    def _connect_pull(self, port):
        """
        Connect to a pull socket on the given port
        :param port:
        :return:
        """
        return DataSocket(
            zmq.Context.instance(), port, zmq.PULL, debug=self._debug, ip_address=self._ip_address
        )

    def get_magellan(self):
        """
        DEPRECATED
        instead use "from pycromanager import Magellan; magellan = Magellan()"

        return an instance of the Micro-Magellan API
        """
        warn('Deprecated. use "from pycromanager import Magellan; magellan = Magellan()"', DeprecationWarning, stacklevel=2)
        return self._construct_java_object("org.micromanager.magellan.api.MagellanAPI")

    def get_core(self):
        """
        DEPRECATED
        instead use "from pycromanager import Core; core = Core()"


        Connect to CMMCore and return object that has its methods

        :return: Python "shadow" object for micromanager core
        """
        warn('Deprecated. use "from pycromanager import Core; core = Core()"', DeprecationWarning, stacklevel=2)
        if hasattr(self, "core"):
            return getattr(self, "core")
        self.core = self._construct_java_object("mmcorej.CMMCore")
        return self.core

    def get_studio(self):
        """
        DEPRECATED use "from pycromanager import Studio; studio = Studio()"

        return an instance of the Studio object that provides access to micro-manager Java APIs
        """
        warn('Deprecated. use "from pycromanager import Studio; studio = Studio()"', DeprecationWarning, stacklevel=2)

        return self._construct_java_object("org.micromanager.Studio")


class _JavaClassFactory:
    """
    This class is responsible for generating subclasses of JavaObjectShadow. Each generated class is kept in a `dict`.
    If a given class has already been generate once it will be returns from the cache rather than re-generating it.
    """

    def __init__(self):
        self.classes = {}

    def create(
        self, serialized_obj: dict, convert_camel_case: bool = True
    ) -> typing.Type["_JavaObjectShadow"]:
        """Create a class (or return a class from the cache) based on the contents of `serialized_object` message."""
        if serialized_obj["class"] in self.classes.keys():  # Return a cached class
            return self.classes[serialized_obj["class"]]
        else:  # Generate a new class since it wasn't found in the cache.
            _java_class: str = serialized_obj["class"]
            python_class_name_translation = _java_class.replace(
                ".", "_"
            )  # Having periods in the name would be problematic.
            _interfaces = serialized_obj["interfaces"]
            static_attributes = {"_java_class": _java_class, "_interfaces": _interfaces}

            fields = {}  # Create a dict of field names with getter and setter funcs.
            for field in serialized_obj["fields"]:
                fields[field] = property(
                    fget=lambda instance, Field=field: instance._access_field(Field),
                    fset=lambda instance, val, Field=field: instance._set_field(Field, val),
                )

            methods = {}  # Create a dict of methods for the class by name.
            methodSpecs = serialized_obj["api"]
            method_names = set([m["name"] for m in methodSpecs])
            # parse method descriptions to make python stand ins
            for method_name in method_names:
                params, methods_with_name, method_name_modified = _parse_arg_names(
                    methodSpecs, method_name, convert_camel_case
                )
                return_type = methods_with_name[0]["return-type"]
                fn = lambda instance, *args, signatures_list=tuple(
                    methods_with_name
                ): instance._translate_call(signatures_list, args, static = _java_class == 'java.lang.Class')
                fn.__name__ = method_name_modified
                fn.__doc__ = "{}.{}: A dynamically generated Java method.".format(
                    _java_class, method_name_modified
                )
                sig = inspect.signature(fn)
                params = [
                    inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
                ] + params  # Add `self` as the first argument.
                return_type = (
                    _JAVA_TYPE_NAME_TO_PYTHON_TYPE[return_type]
                    if return_type in _JAVA_TYPE_NAME_TO_PYTHON_TYPE
                    else return_type
                )
                fn.__signature__ = sig.replace(parameters=params, return_annotation=return_type)
                methods[method_name_modified] = fn

            newclass = type(  # Dynamically create a class to shadow a java class.
                python_class_name_translation,  # Name, based on the original java name
                (_JavaObjectShadow,),  # Inheritance
                {
                    "__init__": lambda instance, socket, serialized_object, bridge: _JavaObjectShadow.__init__(
                        instance, socket, serialized_object, bridge
                    ),
                    **static_attributes,
                    **fields,
                    **methods,
                },
            )

            self.classes[_java_class] = newclass
            return newclass


class _JavaObjectShadow:
    """
    Generic class for serving as a python interface for a java class using a zmq server backend
    """

    _interfaces = (
        None  # Subclasses should fill these out. This class should never be directly instantiated.
    )
    _java_class = None

    def __init__(self, socket, serialized_object, bridge: Bridge):
        self._socket = socket
        self._hash_code = serialized_object["hash-code"]
        self._bridge = bridge
        # register objects with bridge so it can tell Java side to release them before socket shuts down
        socket._register_java_object(self)
        self._closed = False
        # atexit.register(self._close)
        self._close_lock = Lock()

    def _close(self):
        with self._close_lock:
            if self._closed:
                return
            if not hasattr(self, "_hash_code"):
                return  # constructor didnt properly finish, nothing to clean up on java side
            message = {"command": "destructor", "hash-code": self._hash_code}
            if self._bridge._debug:
                "closing: {}".format(self)
            self._socket.send(message)
            reply_json = self._socket.receive()
            if reply_json["type"] == "exception":
                raise Exception(reply_json["value"])
            self._closed = True

    def __del__(self):
        """
        Tell java side this object is garbage collected so it can do the same if needed
        """
        self._close()

    def _access_field(self, name):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {"command": "get-field", "hash-code": self._hash_code, "name": name}
        self._socket.send(message)
        return self._deserialize(self._socket.receive())

    def _set_field(self, name, value):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {
            "command": "set-field",
            "hash-code": self._hash_code,
            "name": name,
            "value": _serialize_arg(value),
        }
        self._socket.send(message)
        reply = self._deserialize(self._socket.receive())

    def _translate_call(self, method_specs, fn_args: tuple, static: bool):
        """
        Translate to appropriate Java method, call it, and return converted python version of its result
        Parameters
        ----------
        args :
             args[0] is list of dictionaries of possible method specifications
        kwargs :
             hold possible polymorphic args, or none
        """
        # args that are none are placeholders to allow for polymorphism and not considered part of the spec
        # fn_args = [a for a in fn_args if a is not None]
        valid_method_spec, deserialize_types = _check_method_args(method_specs, fn_args)
        # args are good, make call through socket, casting the correct type if needed (e.g. int to float)
        message = {
            "command": "run-method",
            "static": static,
            "hash-code": self._hash_code,
            "name": valid_method_spec["name"],
            "argument-types": valid_method_spec["arguments"],
            "argument-deserialization-types": deserialize_types,
        }
        message["arguments"] = _package_arguments(valid_method_spec, fn_args)

        self._socket.send(message)
        recieved = self._socket.receive()
        return self._deserialize(recieved)

    def _deserialize(self, json_return):
        """
        method_spec :
             info about the method that called it
        reply :
            bytes that represents return
        Returns
        -------
        An appropriate python type of the converted value
        """
        if json_return["type"] == "exception":
            raise Exception(json_return["value"])
        elif json_return["type"] == "null":
            return None
        elif json_return["type"] == "primitive":
            return json_return["value"]
        elif json_return["type"] == "string":
            return json_return["value"]
        elif json_return["type"] == "list":
            return [self._deserialize(obj) for obj in json_return["value"]]
        elif json_return["type"] == "object":
            if json_return["class"] == "JSONObject":
                return json.loads(json_return["value"])
            else:
                raise Exception("Unrecognized return class")
        elif json_return["type"] == "unserialized-object":

            # inherit socket from parent object
            obj = self._bridge._deserialize_object(json_return)(
                socket=self._socket, serialized_object=json_return, bridge=self._bridge
            )

            # if object is iterable, go through the elements
            if self._bridge._iterate and hasattr(obj, 'iterator') :
                it = obj.iterator()
                elts = []
                has_next = it.hasNext if hasattr(it, 'hasNext') else it.has_next
                while(has_next()):
                    elts.append(it.next())
                return elts
            else: 
                return obj 
        else:
            return deserialize_array(json_return)


def deserialize_array(json_return):
    """
    Convert a serialized java array to the appropriate numpy type
    Parameters
    ----------
    json_return
    """
    if json_return["type"] in ["byte-array", "int-array", "short-array", "float-array"]:
        decoded = json_return["value"]
        if json_return["type"] == "byte-array":
            return np.frombuffer(decoded, dtype="=u1").copy()
        elif json_return["type"] == "double-array":
            return np.frombuffer(decoded, dtype="=f8").copy()
        elif json_return["type"] == "int-array":
            return np.frombuffer(decoded, dtype="=u4").copy()
        elif json_return["type"] == "short-array":
            return np.frombuffer(decoded, dtype="=u2").copy()
        elif json_return["type"] == "float-array":
            return np.frombuffer(decoded, dtype="=f4").copy()


def _package_arguments(valid_method_spec, fn_args):
    """
    Serialize function arguments and also include description of their Java types

    Parameters
    ----------
    valid_method_spec:
    fn_args :
    """
    arguments = []
    for arg_type, arg_val in zip(valid_method_spec["arguments"], fn_args):
        if isinstance(arg_val, _JavaObjectShadow):
            arguments.append(_serialize_arg(arg_val))
        elif _JAVA_TYPE_NAME_TO_PYTHON_TYPE[arg_type] is object:
            arguments.append(_serialize_arg(arg_val))
        elif arg_val is None:
            arguments.append(_serialize_arg(arg_val))
        elif isinstance(arg_val, np.ndarray):
            arguments.append(_serialize_arg(arg_val))
        else:
            arguments.append(_serialize_arg(_JAVA_TYPE_NAME_TO_PYTHON_TYPE[arg_type](arg_val)))
    return arguments


def _serialize_arg(arg):
    if arg is None:
        return None
    if type(arg) in [bool, str, int, float]:
        return arg  # json handles serialization
    elif type(arg) == np.ndarray:
        return arg.tobytes()
    elif isinstance(arg, _JavaObjectShadow):
        return {"hash-code": arg._hash_code}
    else:
        raise Exception("Unknown argumetn type")


def _check_single_method_spec(method_spec, fn_args):
    """
    Check if a single method specificiation is compatible with the arguments the function recieved

    Parameters
    ----------
    method_spec :
    fn_args :
    """
    if len(method_spec["arguments"]) != len(fn_args):
        return False
    for arg_java_type, arg_val in zip(method_spec["arguments"], fn_args):
        if isinstance(arg_val, _JavaObjectShadow):
            if arg_java_type not in arg_val._interfaces:
                # check that it shadows object of the correct type
                return False
        elif type(arg_val) == np.ndarray:
            # For ND Arrays, need to make sure data types match
            if (
                arg_java_type != "java.lang.Object"
                and arg_val.dtype.type != _JAVA_ARRAY_TYPE_NUMPY_DTYPE[arg_java_type]
            ):
                return False
        elif not any(
            [
                isinstance(arg_val, acceptable_type)
                for acceptable_type in _JAVA_TYPE_NAME_TO_CASTABLE_PYTHON_TYPE[arg_java_type]
            ]
        ) and not (
            arg_val is None and arg_java_type in _JAVA_NON_PRIMITIVES):  # could be null if its an object
            # if a type that gets converted
            return False
    return True


def _check_method_args(method_specs, fn_args):
    """
    Compare python arguments to java arguments to find correct function to call

    Parameters
    ----------
    method_specs :
    fn_args :

    Returns
    -------
    one of the method_specs that is valid
    """
    valid_method_spec = None
    for method_spec in method_specs:
        if _check_single_method_spec(method_spec, fn_args):
            valid_method_spec = method_spec
            break

    if valid_method_spec is None:
        raise Exception(
            "Incorrect arguments. \nExpected {} \nGot {}".format(
                " or ".join([", ".join(method_spec["arguments"]) for method_spec in method_specs]),
                ", ".join([str(type(a)) for a in fn_args]),
            )
        )

    # subclass NDArrays to the appropriate data type so they dont get incorrectly reconstructed as objects
    valid_method_spec = copy.deepcopy(valid_method_spec)
    deserialize_types = []
    for java_arg_class, python_arg_val in zip(valid_method_spec["arguments"], fn_args):
        if isinstance(python_arg_val, np.ndarray):
            deserialize_types.append(
                [
                    ja
                    for ja, npdt in zip(
                        _JAVA_ARRAY_TYPE_NUMPY_DTYPE.keys(), _JAVA_ARRAY_TYPE_NUMPY_DTYPE.values()
                    )
                    if python_arg_val.dtype.type == npdt
                ][0]
            )
        else:
            deserialize_types.append(java_arg_class)

    return valid_method_spec, deserialize_types


def _parse_arg_names(methods, method_name, convert_camel_case):
    method_name_modified = (
        _camel_case_2_snake_case(method_name) if convert_camel_case else method_name
    )
    # all methods with this name and different argument lists
    methods_with_name = [m for m in methods if m["name"] == method_name]
    min_required_args = (
        0
        if len(methods_with_name) == 1 and len(methods_with_name[0]["arguments"]) == 0
        else min([len(m["arguments"]) for m in methods_with_name])
    )
    # sort with largest number of args last so lambda at end gets max num args
    methods_with_name.sort(key=lambda val: len(val["arguments"]))
    method = methods_with_name[-1]  # We only need to evaluate the overload with the most arguments.
    params = []
    unique_argument_names = []
    for arg_index, typ in enumerate(method["arguments"]):
        hint = _CLASS_NAME_MAPPING[typ] if typ in _CLASS_NAME_MAPPING else "object"
        python_type = (
            _JAVA_TYPE_NAME_TO_PYTHON_TYPE[typ] if typ in _JAVA_TYPE_NAME_TO_PYTHON_TYPE else typ
        )
        if hint in unique_argument_names:  # append numbers to end so arg hints have unique names
            i = 1
            while hint + str(i) in unique_argument_names:
                i += 1
            arg_name = hint + str(i)
        else:
            arg_name = hint
        unique_argument_names.append(arg_name)
        # this is how overloading is handled for now, by making default arguments as none, but
        # it might be better to explicitly compare argument types
        if arg_index >= min_required_args:
            default_arg_value = None
        else:
            default_arg_value = inspect.Parameter.empty
        params.append(
            inspect.Parameter(
                name=arg_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default_arg_value,
                annotation=python_type,
            )
        )
    return params, methods_with_name, method_name_modified


def _camel_case_2_snake_case(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

# Used for generating type hints in arguments
_CLASS_NAME_MAPPING = {
    "byte[]": "uint8array",
    "double[]": "float64_array",
    "int[]": "uint32_array",
    "short[]": "int16_array",
    "char[]": "int16_array",
    "float[]": "int16_array",
    "long[]": "int16_array",
    "java.lang.String": "string",
    "boolean": "boolean",
    "double": "float",
    "float": "float",
    "int": "int",
    "long": "int",
    "short": "int",
    "void": "void",
}
#Used for deserializing java arrarys into numpy arrays
_JAVA_ARRAY_TYPE_NUMPY_DTYPE = {
    "boolean[]": np.bool,
    "byte[]": np.uint8,
    "short[]": np.int16,
    "char[]": np.uint16,
    "float[]": np.float32,
    "double[]": np.float64,
    "int[]": np.int32,
    "long[]": np.int64,
}
#used for figuring our which java methods to call and if python args match
_JAVA_TYPE_NAME_TO_PYTHON_TYPE = {
    "boolean": bool,
    "java.lang.Boolean": bool,
    "double": float,
    "java.lang.Double": float,
    "float": float,
    "java.lang.Float": float,
    "int": int,
    "java.lang.Integer": int,
    "long": int,
    "java.lang.Long": int,
    "short": int,
    "java.lang.Short": int,
    "char": int,
    "java.lang.Character": int,
    "byte": int,
    "java.lang.Byte": int,
    "java.lang.String": str,
    "void": None,
    "java.lang.Object": object,
    # maybe could make these more specific to array dtype?
    "byte[]": np.ndarray,
    "short[]": np.ndarray,
    "double[]": np.ndarray,
    "int[]": np.ndarray,
    "char[]": np.ndarray,
    "float[]": np.ndarray,
    "long[]": np.ndarray,
}
# type conversions that allow for autocasting
_JAVA_TYPE_NAME_TO_CASTABLE_PYTHON_TYPE = {
    "boolean": {bool},
    "java.lang.Boolean": {bool},
    "double": {float, int},
    "java.lang.Double": {float, int},
    "long": {int},
    "java.lang.Long": {int},
    "short": {int},
    "java.lang.Short": {int},
    "char": {int},
    "java.lang.Character": {int},
    "byte": {int},
    "java.lang.Byte": {int},
    "float": {float, int},
    "java.lang.Float": {float, int},
    "int": {int},
    "java.lang.Integer": {int},
    "int[]": {np.ndarray},
    "byte[]": {np.ndarray},
    "double[]": {np.ndarray},
    "java.lang.String": {str},
    "void": {None},
    "java.lang.Object": {object},
}
_JAVA_NON_PRIMITIVES = {"byte[]", "double[]", "int[]", "short[]", "char[]", "long[]", "boolean[]",
                        "java.lang.String", "java.lang.Object"}

if __name__ == "__main__":
    # Test basic bridge operations
    import traceback

    b = Bridge()
    try:
        s = b.get_studio()
    except:
        traceback.print_exc()
    try:
        c = b.get_core()
    except:
        traceback.print_exc()
    a = 1
