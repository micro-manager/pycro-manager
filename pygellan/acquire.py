import zmq
import json
import numpy as np
from base64 import standard_b64decode, standard_b64encode
from types import MethodType #dont delete this gets called in an exec
import warnings
import re

class MagellanBridge:

    _DEFAULT_PORTS = {'master': 4827, 'core': 4828, 'magellan': 4829, 'magellan_acq': 4830}
    _EXPECTED_MAGELLAN_VERSION = '2.2.0'

    """
    Master class for communicating with Magellan API
    """
    def __init__(self, port=_DEFAULT_PORTS['master']):
        self.context = zmq.Context()
        # request reply socket
        self._socket = self.context.socket(zmq.REQ)
        self._socket.connect("tcp://127.0.0.1:{}".format(port))
        self.send({'command': 'connect', 'server': 'master'})
        reply_json = self.recieve()
        if reply_json['reply'] != 'success':
            raise Exception(reply_json['message'])
        if 'version' not in reply_json:
            reply_json['version'] = '2.0.0' #before version was added
        if reply_json['version'] != self._EXPECTED_MAGELLAN_VERSION:
            warnings.warn('Version mistmatch between Magellan and Pygellan. '
                            '\nMagellan version: {}\nPygellan expected version: {}'.format(reply_json['version'],
                                                                                    self._EXPECTED_MAGELLAN_VERSION))
        self.core = None
        self.magellan = None

    def send(self, message):
        self._socket.send(bytes(json.dumps(message), 'utf-8'))

    def recieve(self):
        reply = self._socket.recv()
        return json.loads(reply.decode('utf-8'))

    def get_magellan(self):
        """
        Create or get pointer to exisiting magellan object
        :return:
        """
        port = self._DEFAULT_PORTS['magellan']
        if self.magellan is None:
            # request reply socket
            self.send({'command': 'connect', 'server': 'magellan'})
            response = self.recieve()
            if response['reply'] != 'success':
                raise Exception()

            # connect to the dedicated socket for the magellan API
            socket = self.context.socket(zmq.REQ)
            socket.connect("tcp://127.0.0.1:{}".format(port))

            self.magellan = MMJavaClass(socket, response)
        return self.magellan

    def get_core(self, port=_DEFAULT_PORTS['core']):
        """
        Connect to CMMCore and return object that has its methods
        :return:
        """
        if self.core is None:
            # request reply socket
            self.send({'command': 'connect', 'server': 'core'})
            response = self.recieve()
            if response['reply'] != 'success':
                raise Exception()
            # dyanmically get the API from Java server
            socket = self.context.socket(zmq.REQ)
            socket.connect("tcp://127.0.0.1:{}".format(port))
            self.core = MMJavaClass(socket, response)
        return self.core

class MMJavaClass:
    """
    Generic class for serving as a pyhton interface for a micromanager class using a zmq server backend
    """

    _CLASS_NAME_MAPPING = {'boolean': 'boolean', 'byte[]': 'uint8array',
                'double': 'float',   'double[]': 'float64_array', 'float': 'float',
                'int': 'int', 'int[]': 'uint32_array', 'java.lang.String': 'string',
                'long': 'int', 'mmcorej.TaggedImage': 'tagged_image', 'short': 'int', 'void': 'void',
                          'java.util.List': 'list'}

    _CLASS_DTYPE_MAPPING = {'byte[]': np.uint8, 'double[]': np.float64, 'int[]': np.int32}

    #TODO: may want to replace Tagged image with a function that does conversion if passing one in as an arg
    _CLASS_TYPE_MAPPING = {'boolean': bool, 'byte[]': np.ndarray,
                          'double': float, 'double[]': np.ndarray, 'float': float,
                          'int': int, 'int[]': np.ndarray, 'java.lang.String': str,
                          'long': int, 'mmcorej.TaggedImage': None, 'short': int, 'void': None}

    def __init__(self, socket, response, **kwargs):
        self._socket = socket
        self._hash_code = response['hash-code']
        methods = response['api']

        method_names = set([m['name'] for m in methods])
        #parse method descriptions to make python stand ins
        for method_name in method_names:
            method_name_underscores = _camel_case_2_snake_case(method_name)
            #all methods with this name and different argument lists
            methods_with_name = [m for m in methods if m['name'] == method_name]
            min_required_args = 0 if len(methods_with_name) == 1 and len(methods_with_name[0]['arguments']) == 0 else \
                                min([len(m['arguments']) for m in methods_with_name])
            for method in methods_with_name:
                arg_type_hints = [self._CLASS_NAME_MAPPING[t] for t in method['arguments']]
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
                    #this is how polymorphism is handled for now, by making default arguments as none, but
                    #it might be better to explicitly compare argument types
                    if arg_index >= min_required_args:
                        class_arg_names.append(hint + '=' + hint)
                        lambda_arg_names.append(hint + '=None')
                    else:
                        class_arg_names.append(hint)
                        lambda_arg_names.append(hint)

            #use exec so the arguments can have default names that indicate type hints
            exec('fn = lambda {}: MMJavaClass._translate_call(self, {}, {})'.format(','.join(['self'] + lambda_arg_names),
                                                        eval('methods_with_name'),  ','.join(unique_argument_names)))
            #do this one as exec so fn beign undefiend doesnt complain
            exec('setattr(self, method_name_underscores, MethodType(fn, self))')

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
                 correct_type = type(self._CLASS_TYPE_MAPPING[arg_type])
                 if not isinstance(type(arg_val), correct_type):
                     valid_method_spec = None
                 elif type(arg_val) == np.ndarray:
                     #make sure dtypes match
                     if self._CLASS_DTYPE_MAPPING[arg_type] != arg_val.dtype:
                         valid_method_spec = None
            if valid_method_spec is None:
                break
        if valid_method_spec is None:
            raise Exception('Incorrect arguments. \nExpected {} \nGot {}'.format(
                     ' or '.join([','.join(method_spec['arguments']) for method_spec in method_specs]),
                ','.join([type(a) for a in fn_args])))
        #args are good, make call through socket, casting the correct type if needed (e.g. int to float)
        message = {'command': 'run-method', 'hash-code': self._hash_code, 'name': valid_method_spec['name'],
                                'arguments': [self._serialize_arg(
                                self._CLASS_TYPE_MAPPING[arg_type](arg_val)) for
                        arg_type, arg_val in zip(method_spec['arguments'], fn_args)]}
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
            if json_return['class'] == 'TaggedImage':
                tags = json_return['value']['tags']
                pix = np.frombuffer(standard_b64decode(json_return['value']['pix']), dtype='>u2' if
                        json_return['value']['pixel-type'] == 'uint16' else 'uint8')
                if 'width' in tags and 'height' in tags:
                    pix = np.reshape(pix, [tags['height'], tags['width']])
                return pix, tags
            else:
                raise Exception('Unrecognized return class')
        elif json_return['type'] == 'unserialized-object':
            #inherit socket from parent object
            return MMJavaClass(self._socket, json_return)
        elif json_return['type'] == 'byte-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>u1')
        elif json_return['type'] == 'double-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f8')
        elif json_return['type'] == 'int-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>i4')
        elif json_return['type'] == 'float-array':
            return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f4')

    def _serialize_arg(self, arg):
        if type(arg) in [bool, str, int, float]:
            return arg #json handles serialization
        elif type(arg) == np.ndarray:
            return standard_b64encode(arg.tobytes())

def _camel_case_2_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
