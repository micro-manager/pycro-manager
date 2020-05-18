from __future__ import annotations
import json
import re
import time
import typing
import warnings
from base64 import standard_b64encode, standard_b64decode
import inspect
import numpy as np
import zmq


class JavaException(Exception):
    """An exception from the JVM that was sent over the bridge."""


class _PycromanagerEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):  # TODO the way that we transmit arrays is not the same as the way we receive them. This could cause confusion.
            return standard_b64encode(obj.tobytes()).decode('utf-8')
        elif isinstance(obj, JavaObjectShadow):
            return {'hash-code': obj._hash_code}
        elif np.issubdtype(type(obj), np.floating):
            return float(obj)
        elif np.issubdtype(type(obj), np.integer):
            return int(obj)
        return super().default(obj)


def _getDecoder(bridge: Bridge, socket: JavaSocket):
    def decoderObjectHook(dct: dict):
        numpy_type_map = {'byte-array': '>u1', 'double-array': '>f8', 'int-array': '>u4', 'short-array': '>u2', 'float-array': '>f4'}
        if 'type' in dct:
            if dct['type'] == 'exception':
                raise JavaException(dct['value'])
            #TODO aren't null, primitives, strings, and JSONObject already supported natively in JSON, why implement our own handling?
            elif dct['type'] == 'null':
                return None
            elif dct['type'] == 'primitive':
                return dct['value']
            elif dct['type'] == 'string':
                return dct['value']
            elif dct['type'] == 'object':
                if dct['class'] == 'JSONObject':
                    return json.loads(dct['value'], object_hook=decoderObjectHook)
                else:
                    raise Exception('Unrecognized return class')
            elif dct['type'] == 'unserialized-object':
                # inherit socket from parent object
                return bridge.get_class(dct)(socket=socket, serialized_object=dct,bridge=bridge)
            elif dct['type'] in numpy_type_map.keys():  # If we got this far we just assume that it's an array.
                dtype = numpy_type_map[dct['type']]
                return np.frombuffer(standard_b64decode(dct['value']), dtype=dtype).copy()
        return dct  # Return the dict as-is, let json do the default decoding.


class JavaSocket:
    """
    Wrapper for ZMQ socket that sends and recieves dictionaries
    """

    def __init__(self, context, port, type, debug, bridge: Bridge):
        # request reply socket
        self._socket = context.socket(type)
        self._debug = debug
        self._bridge = bridge
        # try:
        if type == zmq.PUSH:
            if debug:
                print('binding {}'.format(port))
            self._socket.bind("tcp://127.0.0.1:{}".format(port))
        else:
            if debug:
                print('connecting {}'.format(port))
            self._socket.connect("tcp://127.0.0.1:{}".format(port))
        # except Exception as e:
        #     print(e.__traceback__)
        # raise Exception('Couldnt connect or bind to port {}'.format(port))

    def send(self, message: dict, timeout=0):
        if message is None:
            message = {}
        #make sure any np types convert to python types so they can be json serialized
        if timeout == 0:
            self._socket.send(bytes(json.dumps(message, cls=_PycromanagerEncoder), 'utf-8'))
        else:
            start = time.time()
            while 1000 * (time.time() - start) < timeout:
                try:
                    self._socket.send(bytes(json.dumps(message, cls=_PycromanagerEncoder), 'utf-8'), flags=zmq.NOBLOCK)
                    return True
                except zmq.ZMQError:
                    pass #ignore, keep trying
            return False

    def receive(self, timeout=0):
        if timeout == 0:
            reply = self._socket.recv()
        else:
            start = time.time()
            reply = None
            while 1000 * (time.time() - start) < timeout:
                try:
                    reply = self._socket.recv(flags=zmq.NOBLOCK)
                    if reply is not None:
                        break
                except zmq.ZMQError:
                    pass #ignore, keep trying
            if reply is None:
                return reply
        message = json.loads(reply.decode('utf-8'), object_hook=_getDecoder(self._bridge, self))
        self._check_exception(message)
        return message

    def _check_exception(self, response):
        if ('type' in response and response['type'] == 'exception'):
            raise Exception(response['value'])

    def close(self):
        self._socket.close()


class Bridge:
    """
    Create an object which acts as a client to a corresponding server running within micro-manager.
    This enables construction and interaction with arbitrary java objects
    """
    _DEFAULT_PORT = 4827
    _EXPECTED_ZMQ_SERVER_VERSION = '2.5.0'


    def __init__(self, port=_DEFAULT_PORT, convert_camel_case=True, debug=False):
        """
        :param port: The port on which the bridge operates
        :type port: int
        :param convert_camel_case: If true, methods for Java objects that are passed across the bridge
            will have their names converted from camel case to underscores. i.e. class.methodName()
            becomes class.method_name()
        :type convert_camel_case: boolean
        :param debug: print helpful stuff for debugging
        :type debug: bool
        """
        self._context = zmq.Context()
        self._convert_camel_case = convert_camel_case
        self._debug = debug
        self._master_socket = JavaSocket(self._context, port, zmq.REQ, debug=debug)
        self._master_socket.send({'command': 'connect', })
        self._class_factory = _JavaClassFactory()
        reply_json = self._master_socket.receive(timeout=500)
        if reply_json is None:
            raise TimeoutError("Socket timed out after 500 milliseconds. Is Micro-Manager running and is the ZMQ server option enabled?")
        if reply_json['type'] == 'exception':
            raise Exception(reply_json['message'])
        if 'version' not in reply_json:
            reply_json['version'] = '2.0.0' #before version was added
        if reply_json['version'] != self._EXPECTED_ZMQ_SERVER_VERSION:
            warnings.warn('Version mistmatch between Java ZMQ server and Python client. '
                            '\nJava ZMQ server version: {}\nPython client expected version: {}'.format(reply_json['version'],
                                                                                           self._EXPECTED_ZMQ_SERVER_VERSION))

    def get_class(self, serialized_object) -> typing.Type[JavaObjectShadow]:
        return self._class_factory.create(serialized_object, convert_camel_case=self._convert_camel_case)

    def construct_java_object(self, classpath, new_socket=False, args=None):
        """
        Create a new instance of a an object on the Java side. Returns a Python "Shadow" of the object, which behaves
        just like the object on the Java side (i.e. same methods, fields). Methods of the object can be inferred at
        runtime using iPython autocomplete

        :param classpath: Full classpath of the java object
        :type classpath: string
        :param new_socket: If true, will create new java object on a new port so that blocking calls will not interfere
            with the bridges master port
        :param args: list of arguments to the constructor, if applicable
        :type args: list
        :return: Python  "Shadow" to the Java object
        """
        if args is None:
            args = []
        # classpath_minus_class = '.'.join(classpath.split('.')[:-1])
        #query the server for constructors matching this classpath
        message = {'command': 'get-constructors', 'classpath': classpath}
        self._master_socket.send(message)
        constructors = self._master_socket.receive()['api']

        methods_with_name = [m for m in constructors if m['name'] == classpath]
        if len(methods_with_name) == 0:
            raise Exception('No valid java constructor found with classpath {}'.format(classpath))
        valid_method_spec = _check_method_args(methods_with_name, args)

        # Calling a constructor, rather than getting return from method
        message = {'command': 'constructor', 'classpath': classpath,
                   'argument-types': valid_method_spec['arguments'],
                   'arguments': _package_arguments(valid_method_spec, args)}
        if new_socket:
            message['new-port'] = True
        self._master_socket.send(message)
        serialized_object = self._master_socket.receive()
        if new_socket:
            socket = JavaSocket(self._context, serialized_object['port'], zmq.REQ)
        else:
            socket = self._master_socket
        return self._class_factory.create(serialized_object)(socket=socket, serialized_object=serialized_object, bridge=self)

    def _connect_push(self, port):
        """
        Connect a push socket on the given port
        :param port:
        :return:
        """
        return JavaSocket(self._context, port, zmq.PUSH, debug=self._debug)

    def _connect_pull(self, port):
        """
        Connect to a pull socket on the given port
        :param port:
        :return:
        """
        return JavaSocket(self._context, port, zmq.PULL, debug=self._debug)


    def get_magellan(self):
        """
        return an instance of the Micro-Magellan API
        """
        return self.construct_java_object('org.micromanager.magellan.api.MagellanAPI')

    def get_core(self):
        """
        Connect to CMMCore and return object that has its methods

        :return: Python "shadow" object for micromanager core
        """
        if hasattr(self, 'core'):
            return getattr(self, 'core')
        self.core = self.construct_java_object('mmcorej.CMMCore')
        return self.core

    def get_studio(self):
        """
        return an instance of the Studio object that provides access to micro-manager Java APIs
        """
        return self.construct_java_object('org.micromanager.Studio')


class _JavaClassFactory:
    """
    This class is responsible for generating subclasses of JavaObjectShadow. Each generated class is kept in a `dict`.
    If a given class has already been generate once it will be returns from the cache rather than re-generating it.
    """
    def __init__(self):
        self.classes = {}

    def create(self, serialized_obj: dict, convert_camel_case: bool = True) -> typing.Type[JavaObjectShadow]:
        """Create a class (or return a class from the cache) based on the contents of `serialized_object` message."""
        if serialized_obj['class'] in self.classes.keys():  # Return a cached class
            return self.classes[serialized_obj['class']]
        else:  # Generate a new class since it wasn't found in the cache.
            _java_class: str = serialized_obj['class']
            python_class_name_translation = _java_class.replace('.', '_')  # Having periods in the name would be problematic.
            _interfaces = serialized_obj['interfaces']
            static_attributes = {'_java_class': _java_class, '_interfaces': _interfaces}

            fields = {}  # Create a dict of field names with getter and setter funcs.
            for field in serialized_obj['fields']:
                getter = lambda instance: instance._access_field(field)
                setter = lambda instance, val: instance._set_field(field, val)
                fields[field] = property(fget=getter, fset=setter)

            methods = {}  # Create a dict of methods for the class by name.
            methodSpecs = serialized_obj['api']
            method_names = set([m['name'] for m in methodSpecs])
            # parse method descriptions to make python stand ins
            for method_name in method_names:
                params, methods_with_name, method_name_modified = _parse_arg_names(methodSpecs, method_name, convert_camel_case)
                return_type = methods_with_name[0]['return-type']
                fn = lambda instance, *args, signatures_list=tuple(methods_with_name): instance._translate_call(signatures_list, args)
                fn.__name__ = method_name_modified
                fn.__doc__ = "{}.{}: A dynamically generated Java method.".format(_java_class, method_name_modified)
                sig = inspect.signature(fn)
                params = [inspect.Parameter('self', inspect.Parameter.POSITIONAL_ONLY)] + params  # Add `self` as the first argument.
                return_type = _JAVA_TYPE_NAME_TO_PYTHON_TYPE[return_type] if return_type in _JAVA_TYPE_NAME_TO_PYTHON_TYPE else return_type
                fn.__signature__ = sig.replace(parameters=params, return_annotation=return_type)
                methods[method_name_modified] = fn

            newclass = type(  # Dynamically create a class to shadow a java class.
                python_class_name_translation,  # Name, based on the original java name
                (JavaObjectShadow,),  # Inheritance
                {'__init__': lambda instance, socket, serialized_object, bridge: JavaObjectShadow.__init__(instance, socket, serialized_object, bridge),
                 **static_attributes, **fields, **methods}
            )

            self.classes[_java_class] = newclass
            print(f'created {newclass.__name__}')
            return newclass


class JavaObjectShadow:
    """
    Generic class for serving as a python interface for a micromanager class using a zmq server backend
    """
    _interfaces = None  # Subclasses should fill these out. This class should never be directly instantiated.
    _java_class = None

    def __init__(self, socket, serialized_object, bridge: Bridge):
        self._socket = socket
        self._hash_code = serialized_object['hash-code']
        self._bridge = bridge

    def __del__(self):
        """
        Tell java side this object is garbage collected so it can do the same if needed
        :return:
        """
        if not hasattr(self, '_hash_code'):
            return #constructor didnt properly finish, nothing to clean up on java side
        message = {'command': 'destructor', 'hash-code': self._hash_code}
        self._socket.send(message)
        reply_json = self._socket.receive()
        if reply_json['type'] == 'exception':
            raise Exception(reply_json['value'])

    def _access_field(self, name):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {'command': 'get-field', 'hash-code': self._hash_code, 'name': name}
        self._socket.send(message)
        return self._deserialize(self._socket.receive())

    def _set_field(self, name, value):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {'command': 'set-field', 'hash-code': self._hash_code, 'name': name, 'value': value}
        self._socket.send(message)
        reply = self._deserialize(self._socket.receive())

    def _translate_call(self, method_specs, fn_args: tuple):
        """
        Translate to appropriate Java method, call it, and return converted python version of its result
        :param args: args[0] is list of dictionaries of possible method specifications
        :param kwargs: hold possible polymorphic args, or none
        :return:
        """
        #args that are none are placeholders to allow for polymorphism and not considered part of the spec
        fn_args = [a for a in fn_args if a is not None]
        valid_method_spec = _check_method_args(method_specs, fn_args)
        #args are good, make call through socket, casting the correct type if needed (e.g. int to float)
        message = {'command': 'run-method', 'hash-code': self._hash_code, 'name': valid_method_spec['name'],
                   'argument-types': valid_method_spec['arguments']}
        message['arguments'] = _package_arguments(valid_method_spec, fn_args)

        self._socket.send(message)
        return self._deserialize(self._socket.receive())


def _package_arguments(valid_method_spec, fn_args):
    """
    Serialize function arguments and also include description of their Java types
    :param valid_method_spec:
    :param fn_args:
    :return:
    """
    arguments = []
    for arg_type, arg_val in zip(valid_method_spec['arguments'], fn_args):
        if isinstance(arg_val, JavaObjectShadow):
            arguments.append(arg_val)
        else:
            arguments.append(_JAVA_TYPE_NAME_TO_PYTHON_TYPE[arg_type](arg_val))
    return arguments


def _check_method_args(method_specs, fn_args):
    """
    Compare python arguments to java arguments to find correct function to call
    :param method_specs:
    :param fn_args:
    :return: one of the method_specs that is valid
    """
    # TODO: check that args can be translated to expected java counterparts (e.g. numpy arrays)
    valid_method_spec = None
    for method_spec in method_specs:
        if len(method_spec['arguments']) != len(fn_args):
            continue
        valid_method_spec = method_spec
        for arg_type, arg_val in zip(method_spec['arguments'], fn_args):
            if isinstance(arg_val, JavaObjectShadow):
                if arg_type not in arg_val._interfaces:
                    # check that it shadows object of the correct type
                    valid_method_spec = None
            elif not isinstance(type(arg_val), type(_JAVA_TYPE_NAME_TO_PYTHON_TYPE[arg_type])):
                # if a type that gets converted
                valid_method_spec = None
            elif type(arg_val) == np.ndarray:
                # For ND Arrays, need to make sure data types match
                if _ARRAY_TYPE_TO_NUMPY_DTYPE[arg_type] != arg_val.dtype:
                    valid_method_spec = None
        # if valid_method_spec is None:
        #     break
    if valid_method_spec is None:
        raise Exception('Incorrect arguments. \nExpected {} \nGot {}'.format(
            ' or '.join([', '.join(method_spec['arguments']) for method_spec in method_specs]),
            ', '.join([str(type(a)) for a in fn_args]) ))
    return valid_method_spec


def _parse_arg_names(methods, method_name, convert_camel_case):
    method_name_modified = _camel_case_2_snake_case(method_name) if convert_camel_case else method_name
    # all methods with this name and different argument lists
    methods_with_name = [m for m in methods if m['name'] == method_name]
    min_required_args = 0 if len(methods_with_name) == 1 and len(methods_with_name[0]['arguments']) == 0 else \
        min([len(m['arguments']) for m in methods_with_name])
    # sort with largest number of args last so lambda at end gets max num args
    methods_with_name.sort(key=lambda val: len(val['arguments']))
    method = methods_with_name[-1]  # We only need to evaluate the overload with the most arguments.
    params = []
    unique_argument_names = []
    for arg_index, typ in enumerate(method['arguments']):
        hint = _CLASS_NAME_MAPPING[typ] if typ in _CLASS_NAME_MAPPING else 'object'
        python_type = _JAVA_TYPE_NAME_TO_PYTHON_TYPE[typ] if typ in _JAVA_TYPE_NAME_TO_PYTHON_TYPE else typ
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
        params.append(inspect.Parameter(name=arg_name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default_arg_value, annotation=python_type))
    return params, methods_with_name, method_name_modified


def _camel_case_2_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


_CLASS_NAME_MAPPING = {'boolean': 'boolean', 'byte[]': 'uint8array',
                       'double': 'float', 'double[]': 'float64_array', 'float': 'float',
                       'int': 'int', 'int[]': 'uint32_array', 'java.lang.String': 'string',
                       'long': 'int', 'short': 'int', 'void': 'void',
                       'java.util.List': 'list'}
_ARRAY_TYPE_TO_NUMPY_DTYPE = {'byte[]': np.uint8, 'double[]': np.float64, 'int[]': np.int32}
_JAVA_TYPE_NAME_TO_PYTHON_TYPE = {'boolean': bool, 'byte[]': np.ndarray,
                                  'double': float, 'double[]': np.ndarray, 'float': float,
                                  'int': int, 'int[]': np.ndarray, 'java.lang.String': str,
                                  'long': int, 'short': int, 'char': int, 'byte': int, 'void': None}

if __name__ == '__main__':
    #Test basic bridge operations
    import traceback
    b = Bridge()
    try:
        s = b.get_studio()
        print(type(s.live()))
    except:
       traceback.print_exc()
    try:
        c = b.get_core()
    except:
        traceback.print_exc()
    a = 1
