import zmq
import json
import numpy as np
from base64 import standard_b64decode, standard_b64encode
from types import MethodType #dont delete this gets called in an exec
import warnings
import re
import time
import json
import multiprocessing
import threading
import queue
from inspect import signature
import copy
import types


# for makign argument type hints. might be mergable with type mapping
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
class JavaSocket:
    """
    Wrapper for ZMQ socket that sends and recieves dictionaries
    """

    def __init__(self, context, port, type, debug):
        # request reply socket
        self._socket = context.socket(type)
        self._debug = debug
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

    def _convert_np_to_python(self, d):
        """
        recursive ply search dictionary and convert any values from numpy floats/ints to
        python floats/ints so they can be hson serialized
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

    def send(self, message, timeout=0):
        if message is None:
            message = {}
        #make sure any np types convert to python types so they can be json serialized
        self._convert_np_to_python(message)
        if timeout == 0:
            self._socket.send(bytes(json.dumps(message), 'utf-8'))
        else:
            start = time.time()
            while 1000 * (time.time() - start) < timeout:
                try:
                    self._socket.send(bytes(json.dumps(message), 'utf-8'), flags=zmq.NOBLOCK)
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
        message = json.loads(reply.decode('utf-8'))
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
    _EXPECTED_ZMQ_SERVER_VERSION = '2.4.0'


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
        reply_json = self._master_socket.receive()
        if reply_json['type'] == 'exception':
            raise Exception(reply_json['message'])
        if 'version' not in reply_json:
            reply_json['version'] = '2.0.0' #before version was added
        if reply_json['version'] != self._EXPECTED_ZMQ_SERVER_VERSION:
            warnings.warn('Version mistmatch between ZMQ server and Pygellan. '
                            '\nZMQ server version: {}\nPygellan expected version: {}'.format(reply_json['version'],
                                                                                           self._EXPECTED_ZMQ_SERVER_VERSION))
        self._constructors = reply_json['api']

    def construct_java_object(self, classpath, new_socket=False, args=[]):
        """
        Create a new intstance of a an object on the Java side. Returns a Python "Shadow" of the object, which behaves
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
        methods_with_name = [m for m in self._constructors if m['name'] == classpath]
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
        return JavaObjectShadow(socket=socket, serialized_object=serialized_object,
                        convert_camel_case=self._convert_camel_case)

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




class JavaObjectShadow:
    """
    Generic class for serving as a pyhton interface for a micromanager class using a zmq server backend
    """

    def __init__(self, socket, serialized_object=None, convert_camel_case=True):
        self._java_class = serialized_object['class']
        self._socket = socket
        self._hash_code = serialized_object['hash-code']
        self._convert_camel_case = convert_camel_case
        self._interfaces = serialized_object['interfaces']
        for field in serialized_object['fields']:
            exec('JavaObjectShadow.{} = property(lambda instance: instance._access_field(\'{}\'),'
                 'lambda instance, val: instance._set_field(\'{}\', val))'.format(field, field, field))
        methods = serialized_object['api']

        method_names = set([m['name'] for m in methods])
        #parse method descriptions to make python stand ins
        for method_name in method_names:
            lambda_arg_names, unique_argument_names, methods_with_name, \
                method_name_modified = _parse_arg_names(methods, method_name, self._convert_camel_case)
            #use exec so the arguments can have default names that indicate type hints
            exec('fn = lambda {}: JavaObjectShadow._translate_call(self, {}, {})'.format(','.join(['self'] + lambda_arg_names),
                                                        eval('methods_with_name'),  ','.join(unique_argument_names)))
            #do this one as exec also so "fn" being undefiend doesnt complain
            exec('setattr(self, method_name_modified, MethodType(fn, self))')


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

    def __repr__(self):
        #convenience for debugging
        return 'JavaObjectShadow for : ' + self._java_class

    def _access_field(self, name, *args):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {'command': 'get-field', 'hash-code': self._hash_code, 'name': name}
        self._socket.send(message)
        return self._deserialize(self._socket.receive())

    def _set_field(self, name, value, *args):
        """
        Return a python version of the field with a given name
        :return:
        """
        message = {'command': 'set-field', 'hash-code': self._hash_code, 'name': name, 'value': _serialize_arg(value)}
        self._socket.send(message)
        reply = self._deserialize(self._socket.receive())

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
        valid_method_spec = _check_method_args(method_specs, fn_args)
        #args are good, make call through socket, casting the correct type if needed (e.g. int to float)
        message = {'command': 'run-method', 'hash-code': self._hash_code, 'name': valid_method_spec['name'],
                   'argument-types': valid_method_spec['arguments']}
        message['arguments'] = _package_arguments(valid_method_spec, fn_args)

        self._socket.send(message)
        return self._deserialize(self._socket.receive())

    def _deserialize(self, json_return):
        """
        :param method_spec: info about the method that called it
        :param reply: bytes that represents return
        :return: an appropriate python type of the converted value
        """
        if json_return['type'] == 'exception':
            raise Exception(json_return['value'])
        elif json_return['type'] == 'null':
            return None
        elif json_return['type'] == 'primitive':
            return json_return['value']
        elif json_return['type'] == 'string':
            return json_return['value']
        elif json_return['type'] == 'list':
            return [self._deserialize(obj) for obj in json_return['value']]
        elif json_return['type'] == 'object':
            if json_return['class'] == 'JSONObject':
                return json.loads(json_return['value'])
            else:
                raise Exception('Unrecognized return class')
        elif json_return['type'] == 'unserialized-object':
            #inherit socket from parent object
            return JavaObjectShadow(socket=self._socket, serialized_object=json_return,
                                    convert_camel_case=self._convert_camel_case)
        else:
            return deserialize_array(json_return)

############ Utility functions ############
def serialize_array(array):
    return standard_b64encode(array.tobytes()).decode('utf-8')

def deserialize_array(json_return):
    """
    Convet a serialized java array to the appropriate numpy type
    :param json_return:
    :return:
    """
    if json_return['type'] == 'byte-array':
        return np.frombuffer(standard_b64decode(json_return['value']), dtype='>u1').copy()
    elif json_return['type'] == 'double-array':
        return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f8').copy()
    elif json_return['type'] == 'int-array':
        return np.frombuffer(standard_b64decode(json_return['value']), dtype='>i4').copy()
    elif json_return['type'] == 'short-array':
        return np.frombuffer(standard_b64decode(json_return['value']), dtype='>i2').copy()
    elif json_return['type'] == 'float-array':
        return np.frombuffer(standard_b64decode(json_return['value']), dtype='>f4').copy()

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
            arguments.append(_serialize_arg(arg_val))
        else:
            arguments.append(_serialize_arg(_JAVA_TYPE_NAME_TO_PYTHON_TYPE[arg_type](arg_val)))
    return arguments

def _serialize_arg(arg):
    if type(arg) in [bool, str, int, float]:
        return arg #json handles serialization
    elif type(arg) == np.ndarray:
        return serialize_array(arg)
    elif isinstance(arg, JavaObjectShadow):
        return {'hash-code': arg._hash_code}
    else:
        raise Exception('Unknown argumetn type')

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
    # dont delete because this is used in the exec
    method_name_modified = _camel_case_2_snake_case(method_name) if convert_camel_case else method_name
    # all methods with this name and different argument lists
    methods_with_name = [m for m in methods if m['name'] == method_name]
    min_required_args = 0 if len(methods_with_name) == 1 and len(methods_with_name[0]['arguments']) == 0 else \
        min([len(m['arguments']) for m in methods_with_name])
    # sort with largest number of args last so lambda at end gets max num args
    methods_with_name.sort(key=lambda val: len(val['arguments']))
    for method in methods_with_name:
        arg_type_hints = []
        for typ in method['arguments']:
            arg_type_hints.append(_CLASS_NAME_MAPPING[typ]
                                  if typ in _CLASS_NAME_MAPPING else 'object')
        lambda_arg_names = []
        class_arg_names = []
        unique_argument_names = []
        for arg_index, hint in enumerate(arg_type_hints):
            if hint in unique_argument_names:
                # append numbers to end so arg hints have unique names
                i = 1
                while hint + str(i) in unique_argument_names:
                    i += 1
                hint += str(i)
            unique_argument_names.append(hint)
            # this is how overloading is handled for now, by making default arguments as none, but
            # it might be better to explicitly compare argument types
            if arg_index >= min_required_args:
                class_arg_names.append(hint + '=' + hint)
                lambda_arg_names.append(hint + '=None')
            else:
                class_arg_names.append(hint)
                lambda_arg_names.append(hint)
    return lambda_arg_names, unique_argument_names, methods_with_name, method_name_modified

def _camel_case_2_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class Acquisition():

    def __init__(self, directory=None, name=None, image_process_fn=None,
                 pre_hardware_hook_fn=None, post_hardware_hook_fn=None,
                 magellan_acq_index=None, process=True, debug=False):
        """
        :param directory: saving directory for this acquisition. Required unless an image process function will be
            implemented that diverts images from saving
        :type directory: str
        :param name: Saving name for the acquisition. Required unless an image process function will be
            implemented that diverts images from saving
        :type name: str
        :param image_process_fn: image processing function that will be called on each image that gets acquired.
            Can either take two arguments (image, metadata) where image is a numpy array and metadata is a dict
            containing the corresponding iamge metadata. Or a 4 argument version is accepted, which accepts (image,
            metadata, bridge, queue), where bridge and queue are an instance of the pycromanager.acquire.Bridge
            object for the purposes of interacting with arbitrary code on the Java side (such as the micro-manager
            core), and queue is a Queue objects that holds upcomning acquisition events. Both version must either
            return
        :param pre_hardware_hook_fn: hook function that will be run just before the hardware is updated before acquiring
            a new image. Accepts either one argument (the current acquisition event) or three arguments (current event,
            bridge, event Queue)
        :param post_hardware_hook_fn: hook function that will be run just before the hardware is updated before acquiring
            a new image. Accepts either one argument (the current acquisition event) or three arguments (current event,
            bridge, event Queue)
        :param magellan_acq_index: run this acquisition using the settings specified at this position in the main
            GUI of micro-magellan (micro-manager plugin). This index starts at 0
        :type magellan_acq_index: int
        :param process: (Experimental) use multiprocessing instead of multithreading for acquisition hooks and image
            processors
        :type process: boolean
        :param debug: print debugging stuff
        :type debug: boolean
        """
        self.bridge = Bridge(debug=debug)
        self._debug = debug


        if magellan_acq_index is not None:
            magellan_api = self.bridge.get_magellan()
            self.acq = magellan_api.create_acquisition(magellan_acq_index)
            self._event_queue = None
        else:
            # TODO: call different constructor if direcotyr and name are None
            # Create thread safe queue for events so they can be passed from multiple processes
            self._event_queue = multiprocessing.Queue()
            core = self.bridge.get_core()
            acq_manager = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcquisitionFactory', args=[core])
            self.acq = acq_manager.create_acquisition(directory, name)

        if image_process_fn is not None:
            processor = self.bridge.construct_java_object('org.micromanager.remote.RemoteImageProcessor')
            self.acq.add_image_processor(processor)
            self._start_processor(processor, image_process_fn, self._event_queue, process=process)

        if pre_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcqHook')
            self._start_hook(hook, pre_hardware_hook_fn, self._event_queue, process=process)
            self.acq.add_hook(hook, self.acq.BEFORE_HARDWARE_HOOK, args=[self.acq])
        if post_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcqHook', args=[self.acq])
            self._start_hook(hook, post_hardware_hook_fn, self._event_queue, process=process)
            self.acq.add_hook(hook, self.acq.AFTER_HARDWARE_HOOK)

        self.acq.start()

        if magellan_acq_index is None:
            event_port = self.acq.get_event_port()

            def event_sending_fn():
                bridge = Bridge(debug=debug)
                event_socket = bridge._connect_push(event_port)
                while True:
                    events = self._event_queue.get(block=True)
                    if events is None:
                        #Poison, time to shut down
                        event_socket.send({'events': [{'special': 'acquisition-end'}]})
                        event_socket.close()
                        return
                    event_socket.send({'events': events if type(events) == list else [events]})

            self.event_process = multiprocessing.Process(target=event_sending_fn, args=(), name='Event sending')
                    # if multiprocessing else threading.Thread(target=event_sending_fn, args=(), name='Event sending')
            self.event_process.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._event_queue is not None: #magellan acquisitions dont have this
            # this should shut down storage and viewer as apporpriate
            self._event_queue.put(None)
        #now wait on it to finish
        self.await_completion()

    def await_completion(self):
        """
        Wait for acquisition to finish and resources to be cleaned up
        """
        self.acq.close()

    def acquire(self, events):
        """
        Submit an event or a list of events for acquisition. Optimizations (i.e. taking advantage of
        hardware synchronization, where available), will take place across this list of events, but not
        over multiple calls of this method. A single event is a python dictionary with a specific structure

        :param events: single event (i.e. a dictionary) or a list of events
        """
        self._event_queue.put(events)

    def _start_hook(self, remote_hook, remote_hook_fn, event_queue, process):
        hook_connected_evt = multiprocessing.Event() if process else threading.Event()

        pull_port = remote_hook.get_pull_port()
        push_port = remote_hook.get_push_port()

        def other_thread_fn():
            bridge = Bridge(debug=self._debug)

            push_socket = bridge._connect_push(pull_port)
            pull_socket = bridge._connect_pull(push_port)
            hook_connected_evt.set()

            while True:
                event_msg = pull_socket.receive()

                if 'special' in event_msg and event_msg['special'] == 'acquisition-end':
                    push_socket.send({})
                    push_socket.close()
                    pull_socket.close()
                    return
                else:
                    params = signature(remote_hook_fn).parameters
                    if len(params) == 1:
                        new_event_msg = remote_hook_fn(event_msg)
                    elif len(params) == 3:
                        new_event_msg = remote_hook_fn(event_msg, bridge, event_queue)
                    else:
                        raise Exception('Incorrect number of arguments for hook function. Must be 2 or 4')

                push_socket.send(new_event_msg)

        hook_thread = multiprocessing.Process(target=other_thread_fn, args=(), name='AcquisitionHook') if process\
            else threading.Thread(target=other_thread_fn, args=(), name='AcquisitionHook')
        hook_thread.start()

        hook_connected_evt.wait()  # wait for push/pull sockets to connect

    def _start_processor(self, processor, process_fn, event_queue, process):
        # this must start first
        processor.start_pull()

        sockets_connected_evt = multiprocessing.Event() if process else threading.Event()

        pull_port = processor.get_pull_port()
        push_port = processor.get_push_port()
        def other_thread_fn():
            bridge = Bridge(debug=self._debug)
            push_socket = bridge._connect_push(pull_port)
            pull_socket = bridge._connect_pull(push_port)
            if self._debug:
                print('image processing sockets connected')
            sockets_connected_evt.set()

            while True:
                message = None
                while message is None:
                    message = pull_socket.receive(timeout=30) #check for new message

                if 'special' in message and message['special'] == 'finished':
                    push_socket.send(message) #Continue propagating the finihsed signal
                    push_socket.close()
                    pull_socket.close()
                    return

                metadata = message['metadata']
                pixels = deserialize_array(message['pixels'])
                image = np.reshape(pixels, [metadata['Width'], metadata['Height']])

                params = signature(process_fn).parameters
                if len(params) == 2:
                    processed = process_fn(image, metadata)
                elif len(params) == 4:
                    processed = process_fn(image, metadata, bridge, event_queue)
                else:
                    raise Exception('Incorrect number of arguments for image processing function, must be 2 or 4')
                if processed is None:
                    continue
                if len(processed) != 2:
                    raise Exception('If image is returned, it must be of the form (pixel, metadata)')
                if not processed[0].dtype == pixels.dtype:
                    raise Exception('Processed image pixels must have same dtype as input image pixels, '
                                    'but instead they were {} and {}'.format(processed[0].dtype, pixels.dtype))

                processed_img = {'pixels': serialize_array(processed[0]), 'metadata': processed[1]}
                push_socket.send(processed_img)

        self.processor_thread = multiprocessing.Process(target=other_thread_fn, args=(), name='ImageProcessor'
                        ) if multiprocessing else threading.Thread(target=other_thread_fn, args=(),  name='ImageProcessor')
        self.processor_thread.start()

        sockets_connected_evt.wait()  # wait for push/pull sockets to connect
        processor.start_push()


def multi_d_acquisition_events(num_time_points=1, time_interval_s=0, z_start=None, z_end=None, z_step=None,
                channel_group=None, channels=None, channel_exposures_ms=None, xy_positions=None, order='tpcz'):
    """
    Convenience function for generating the events of a typical multi-dimensional acquisition (i.e. an
    acquisition with some combination of multiple timepoints, channels, z-slices, or xy positions)

    :param num_time_points: How many time points if it is a timelapse
    :type num_time_points: int
    :param time_interval_s: the minimum interval between consecutive time points in seconds. Keep at 0 to go as
        fast as possible
    :type time_interval_s: float
    :param z_start: z-stack starting position, in µm
    :type z_start: float
    :param z_end: z-stack ending position, in µm
    :type z_end: float
    :param z_step: step size of z-stack, in µm
    :type z_step: float
    :param channel_group: name of the channel group (which should correspond to a config group in micro-manager)
    :type channel_group: str
    :param channels: list of channel names, which correspond to possible settings of the config group (e.g. ['DAPI',
        'FITC'])
    :type channels: list of strings
    :param channel_exposures_ms: list of camera exposure times corresponding to each channel. The length of this list
        should be the same as the the length of the list of channels
    :type channel_exposures_ms: list of floats or ints
    :param xy_positions: N by 2 numpy array where N is the number of XY stage positions, and the 2 are the X and Y
        coordinates
    :type xy_positions: numpy array
    :param order: string that specifies the order of different dimensions. Must have some ordering of the letters
        c, t, p, and z. For example, 'tcz' would run a timelapse where z stacks would be acquired at each channel in
        series. 'pt' would move to different xy stage positions and run a complete timelapse at each one before moving
        to the next
    :type order: str

    :return: a list of acquisition events to run the specified acquisition
    """


    def generate_events(event, order):
        if len(order) == 0:
            yield event
            return
        elif order[0] == 't' and num_time_points != 1:
            time_indices = np.arange(num_time_points)
            for time_index in time_indices:
                new_event = copy.deepcopy(event)
                new_event['axes']['time'] = time_index
                if time_interval_s != 0:
                    new_event['min_start_time'] = time_index * time_interval_s
                yield generate_events(new_event, order[1:])
        elif order[0] == 'z' and z_start is not None and z_end is not None and z_step is not None:
            z_positions = np.arange(z_start, z_end, z_step)
            for z_index, z_position in enumerate(z_positions):
                new_event = copy.deepcopy(event)
                new_event['axes']['z'] = z_index
                new_event['z'] = z_position
                yield generate_events(new_event, order[1:])
        elif order[0] == 'p' and xy_positions is not None:
            for p_index, xy in enumerate(xy_positions):
                new_event = copy.deepcopy(event)
                new_event['axes']['position'] = p_index
                new_event['x'] = xy[0]
                new_event['y'] = xy[1]
                yield generate_events(new_event, order[1:])
        elif order[0] == 'c' and channel_group is not None and channels is not None:
            for i in range(len(channels)):
                new_event = copy.deepcopy(event)
                new_event['channel'] = {'group': channel_group, 'config': channels[i]}
                if channel_exposures_ms is not None:
                    new_event['exposure'] = i
                yield generate_events(new_event, order[1:])
        else:
            #this axis appears to be missing
            yield generate_events(event, order[1:])

    #collect all events into a single list
    base_event = {'axes': {}}
    events = []
    def appender(next):
        if isinstance(next, types.GeneratorType):
            for n in next:
                appender(n)
        else:
            events.append(next)

    appender(generate_events(base_event, order))
    return events
