import zmq
import json
import numpy as np
from base64 import standard_b64decode, standard_b64encode
from types import MethodType #dont delete this gets called in an exec
import warnings
import re

class PygellanBridge:

    _DEFAULT_PORT = 4827
    _EXPECTED_ZMQ_SERVER_VERSION = '2.3.0'

    """
    Master class for communicating with Magellan API
    """
    def __init__(self, port=_DEFAULT_PORT, convert_camel_case=True):
        self._convert_camel_case = convert_camel_case
        self._context = zmq.Context()
        # request reply socket
        self._master_socket = self._context.socket(zmq.REQ)
        self._master_socket.connect("tcp://127.0.0.1:{}".format(port))
        self._send({'command': 'connect', })
        reply_json = self._receive()
        if reply_json['type'] == 'exception':
            raise Exception(reply_json['message'])
        if 'version' not in reply_json:
            reply_json['version'] = '2.0.0' #before version was added
        if reply_json['version'] != self._EXPECTED_ZMQ_SERVER_VERSION:
            warnings.warn('Version mistmatch between ZMQ server and Pygellan. '
                            '\nZMQ server version: {}\nPygellan expected version: {}'.format(reply_json['version'],
                                                                                           self._EXPECTED_ZMQ_SERVER_VERSION))
        self._next_port = port

    def __del__(self):
        #close all sockets
        for attr_name in dir(self):
            if '_socket_' in attr_name:
                shadow = getattr(self, attr_name)
                del shadow
        #close master socker
        self._master_socket.close()
        self._context.term()

    def _send(self, message):
        self._master_socket.send(bytes(json.dumps(message), 'utf-8'))

    def _receive(self):
        reply = self._master_socket.recv()
        return json.loads(reply.decode('utf-8'))

    def construct_java_object(self, classpath, new_socket=False):
        """
        Get a python object that shadows Java object, optionally with its own server
        :return:
        """
        if not new_socket:
            socket = self._master_socket
        name = '_root_java_obj_' + classpath.lower().replace('.', '_')
        if not hasattr(self, name):
            if new_socket:
                self._next_port += 1
                # Create a new request reply socket with this class as the master
                self._send({'command': 'constructor', 'classpath': classpath, 'port': self._next_port})
                response = self._receive()
                if ('type' in response and response['type'] == 'exception'):
                    raise Exception(response['value'])
                if response['type'] == 'exception':
                    raise Exception(response['message'])
                # connect to the dedicated socket for the magellan API
                socket = self._context.socket(zmq.REQ)
                socket.connect("tcp://127.0.0.1:{}".format(self._next_port))
                setattr(self, name, JavaObjectShadow(socket, response, None, self._convert_camel_case))
            else:
                self._send({'command': 'constructor', 'classpath': classpath})
                response = self._receive()
                if ('type' in response and response['type'] == 'exception'):
                    raise Exception(response['value'])
                if response['type'] == 'exception':
                    raise Exception(response['message'])
                setattr(self, name, JavaObjectShadow(socket, response, None, self._convert_camel_case))
        return getattr(self, name)

    def get_magellan(self):
        """
        Create or get pointer to exisiting magellan object
        :return:
        """
        return self.construct_java_object('org.micromanager.magellan.api.MagellanAPI', new_socket=True)

    def get_core(self):
        """
        Connect to CMMCore and return object that has its methods
        :return:
        """
        return self.construct_java_object('mmcorej.CMMCore', new_socket=True)

    def get_studio(self):
        """
        Connect to CMMCore and return object that has its methods
        :return:
        """
        return self.construct_java_object('org.micromanager.Studio', new_socket=True)

class JavaObjectShadow:
    """
    Generic class for serving as a pyhton interface for a micromanager class using a zmq server backend
    """

    _CLASS_NAME_MAPPING = {'boolean': 'boolean', 'byte[]': 'uint8array',
                'double': 'float',   'double[]': 'float64_array', 'float': 'float',
                'int': 'int', 'int[]': 'uint32_array', 'java.lang.String': 'string',
                'long': 'int', 'short': 'int', 'void': 'void',
                          'java.util.List': 'list'}
    _CLASS_DTYPE_MAPPING = {'byte[]': np.uint8, 'double[]': np.float64, 'int[]': np.int32}
    _CLASS_TYPE_MAPPING = {'boolean': bool, 'byte[]': np.ndarray,
                          'double': float, 'double[]': np.ndarray, 'float': float,
                          'int': int, 'int[]': np.ndarray, 'java.lang.String': str,
                          'long': int, 'short': int, 'void': None}

    def __init__(self, socket, serialized_object, parent, convert_camel_case=True, new_socket=False, **kwargs):
        self._java_class = serialized_object['class']
        self._socket = socket
        self._parent = parent
        self._hash_code = serialized_object['hash-code']
        self._convert_camel_case = convert_camel_case
        self._interfaces = serialized_object['interfaces']
        for field in serialized_object['fields']:
            exec('JavaObjectShadow.{} = property(lambda instance: instance._access_field(\'{}\'))'.format(field, field))
        methods = serialized_object['api']

        method_names = set([m['name'] for m in methods])
        #parse method descriptions to make python stand ins
        for method_name in method_names:
            #dont delete because this is used in the exec
            method_name_modified = _camel_case_2_snake_case(method_name) if self._convert_camel_case else method_name
            #all methods with this name and different argument lists
            methods_with_name = [m for m in methods if m['name'] == method_name]
            min_required_args = 0 if len(methods_with_name) == 1 and len(methods_with_name[0]['arguments']) == 0 else \
                                min([len(m['arguments']) for m in methods_with_name])
            #sort with largest number of args last so lambda at end gets max num args
            methods_with_name.sort(key=lambda val: len(val['arguments']))
            for method in methods_with_name:
                arg_type_hints = []
                for typ in method['arguments']:
                    arg_type_hints.append(self._CLASS_NAME_MAPPING[typ] if typ in self._CLASS_NAME_MAPPING else 'object')
                lambda_arg_names = []
                class_arg_names = []
                unique_argument_names = []
                for arg_index, hint in enumerate(arg_type_hints):
                    if hint in unique_argument_names:
                        #append numbers to end so arg hints have unique names
                        i = 1
                        while hint + str(i) in unique_argument_names:
                            i += 1
                        hint += str(i)
                    unique_argument_names.append(hint)
                    #this is how overloading is handled for now, by making default arguments as none, but
                    #it might be better to explicitly compare argument types
                    if arg_index >= min_required_args:
                        class_arg_names.append(hint + '=' + hint)
                        lambda_arg_names.append(hint + '=None')
                    else:
                        class_arg_names.append(hint)
                        lambda_arg_names.append(hint)

            #use exec so the arguments can have default names that indicate type hints
            exec('fn = lambda {}: JavaObjectShadow._translate_call(self, {}, {})'.format(','.join(['self'] + lambda_arg_names),
                                                        eval('methods_with_name'),  ','.join(unique_argument_names)))
            #do this one as exec so fn beign undefiend doesnt complain
            exec('setattr(self, method_name_modified, MethodType(fn, self))')

    def __del__(self):
        """
        Tell java side this object is garbage collected so it can do the same if needed
        :return:
        """
        message = {'command': 'destructor', 'hash-code': self._hash_code}
        self._socket.send(bytes(json.dumps(message), 'utf-8'))
        reply = self._socket.recv()
        reply_json = json.loads(reply.decode('utf-8'))
        if reply_json['type'] == 'exception':
            raise Exception(reply_json['value'])
        if self._parent is None:
            #if root object destructor called, close the socket. Child objects maintain references to parent
            #so parent shouldn't be garbage collected if references to child object remain
            self._socket.close()

    def __repr__(self):
        #convenience for debugging
        return 'JavaObjectShadow for : ' + self._java_class

    def _access_field(self, name, *args):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {'command': 'get-field', 'hash-code': self._hash_code, 'name': name}
        self._socket.send(bytes(json.dumps(message), 'utf-8'))
        reply = self._socket.recv()
        return self._deserialize_return(reply)

    def _translate_call(self, *args):
        """
        Translate to appropriate Java method, call it, and return converted python version of its result
        :param args: args[0] is list of dictionaries of possible method specifications
        :param kwargs: hold possible polymorphic args, or none
        :return:
        """
        method_specs = args[0]
        #args that are none are placeholders to allow for polymorphism and not considered part of the spec
        fn_args = [a for a in args[1:] if a is not None]
        #TODO: check that args can be translated to expected java counterparts (e.g. numpy arrays)
        valid_method_spec = None
        for method_spec in method_specs:
            if len(method_spec['arguments']) != len(fn_args):
                continue
            valid_method_spec = method_spec
            for arg_type, arg_val in zip(method_spec['arguments'], fn_args):
                 if isinstance(arg_val, JavaObjectShadow):
                     if arg_type not in arg_val._interfaces:
                        #check that it shadows object of the correct type
                        valid_method_spec = None
                 elif not isinstance(type(arg_val), type(self._CLASS_TYPE_MAPPING[arg_type])):
                     # if a type that gets converted
                     valid_method_spec = None
                 elif type(arg_val) == np.ndarray:
                     #For ND Arrays, need to make sure data types match
                     if self._CLASS_DTYPE_MAPPING[arg_type] != arg_val.dtype:
                         valid_method_spec = None
            if valid_method_spec is None:
                break
        if valid_method_spec is None:
            raise Exception('Incorrect arguments. \nExpected {} \nGot {}'.format(
                     ' or '.join([','.join(method_spec['arguments']) for method_spec in method_specs]),
                ','.join([type(a) for a in fn_args])))
        #args are good, make call through socket, casting the correct type if needed (e.g. int to float)
        message = {'command': 'run-method', 'hash-code': self._hash_code, 'name': valid_method_spec['name']}
        message['arguments'] = []
        for arg_type, arg_val in zip(valid_method_spec['arguments'], fn_args):
            if isinstance(arg_val, JavaObjectShadow):
                message['arguments'].append(self._serialize_arg(arg_val))
            else:
                message['arguments'].append(self._serialize_arg(self._CLASS_TYPE_MAPPING[arg_type](arg_val)))

        self._socket.send(bytes(json.dumps(message), 'utf-8'))
        reply = self._socket.recv()
        return self._deserialize_return(reply)

    def _deserialize_return(self, reply):
        """
        :param method_spec: info about the method that called it
        :param reply: bytes that represents return
        :return: an appropriate python type of the converted value
        """
        if type(reply) != dict:
            json_return = json.loads(reply.decode('utf-8'))
        else:
            json_return = reply
        if json_return['type'] == 'exception':
            raise Exception(json_return['value'])
        elif json_return['type'] == 'none':
            return None
        elif json_return['type'] == 'primitive':
            return json_return['value']
        elif json_return['type'] == 'string':
            return json_return['value']
        elif json_return['type'] == 'list':
            return [self._deserialize_return(obj) for obj in json_return['value']]
        elif json_return['type'] == 'object':
            if json_return['class'] == 'JSONObject':
                return json.loads(json_return['value'])
            else:
                raise Exception('Unrecognized return class')
        elif json_return['type'] == 'unserialized-object':
            #inherit socket from parent object
            return JavaObjectShadow(self._socket, json_return, self, self._convert_camel_case)
        elif json_return['type'] == 'byte-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>u1')
        elif json_return['type'] == 'double-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f8')
        elif json_return['type'] == 'int-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>i4')
        elif json_return['type'] == 'short-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>i2')
        elif json_return['type'] == 'float-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f4')

    def _serialize_arg(self, arg):
        if type(arg) in [bool, str, int, float]:
            return arg #json handles serialization
        elif type(arg) == np.ndarray:
            return standard_b64encode(arg.tobytes())
        elif isinstance(arg, JavaObjectShadow):
            return {'hash-code': arg._hash_code}
        else:
            raise Exception('Unknown argumetn type')

def _camel_case_2_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
