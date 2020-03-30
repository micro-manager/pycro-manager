from pygellan.acquire import PygellanBridge, deserialize_array, serialize_array
import numpy as np
import json
import matplotlib.pyplot as plt
import multiprocessing
import threading
import queue
from inspect import signature



class Acquisition():

    def __init__(self, directory, name, channel_group=None, image_process_fn=None,
                 pre_hardware_hook_fn=None, post_hardware_hook_fn=None, multiprocessing=False):
        self.bridge = PygellanBridge()

        # Create thread safe queue for events so they can be passed from multiple processes
        self._event_queue = multiprocessing.Queue() if multiprocessing else queue.Queue()

        core = self.bridge.get_core()
        acq_manager = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcquisitionFactory', args=[core])
        self.acq = acq_manager.create_acquisition(directory, name, channel_group)
        if image_process_fn is not None:
            processor = self.bridge.construct_java_object('org.micromanager.remote.RemoteImageProcessor')
            self.acq.add_image_processor(processor)
            self._start_processor(processor, image_process_fn, self._event_queue, multiprocessing=multiprocessing)

        if pre_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcqHook')
            self._start_hook(hook, pre_hardware_hook_fn, self._event_queue, multiprocessing=multiprocessing)
            self.acq.add_hook(hook, self.acq.BEFORE_HARDWARE_HOOK, args=[self.acq])
        if post_hardware_hook_fn is not None:
            hook = self.bridge.construct_java_object('org.micromanager.remote.RemoteAcqHook', args=[self.acq])
            self._start_hook(hook, post_hardware_hook_fn, self._event_queue, multiprocessing=multiprocessing)
            self.acq.add_hook(hook, self.acq.AFTER_HARDWARE_HOOK)

        self.acq.start()
        event_port = self.acq.get_event_port()


        def event_sending_fn():
            bridge = PygellanBridge()
            event_socket = bridge.connect_push(event_port)
            while True:
                events = self._event_queue.get(block=True)
                if events is None:
                    #Poison, time to shut down
                    event_socket.send({'events': [{'special': 'acquisition-end'}]})
                    event_socket.close()
                    return
                event_socket.send({'events': events if type(events) == list else [events]})

        self.event_process = multiprocessing.Process(target=event_sending_fn, args=(), name='Event sending') if \
                    multiprocessing else threading.Thread(target=event_sending_fn, args=(), name='Event sending')
        self.event_process.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """
        Finish the acquisition and release all resources related to remote connection
        :return:
        """
        #this should shut down storage and viewer as apporpriate
        self._event_queue.put(None)

    def acquire(self, events):
        """
        Submit an event or a list of events for acquisition. Optimizations (i.e. taking advantage of
        hardware synchronization, where available), will take place across this list of events, but not
        over multiple calls of this method. A single event is a python dictionary with a specific structure

        :param events: single event (i.e. a dictionary) or a list of events
        :return:
        """
        self._event_queue.put(events)

    def _start_hook(self, remote_hook, remote_hook_fn, event_queue, multiprocessing):
        hook_connected_evt = multiprocessing.Event() if multiprocessing else threading.Event()

        pull_port = remote_hook.get_pull_port()
        push_port = remote_hook.get_push_port()

        def other_thread_fn():
            bridge = PygellanBridge()
            # setattr(remote_hook_fn, 'bridge', bridge)

            push_socket = bridge.connect_push(pull_port)
            pull_socket = bridge.connect_pull(push_port)
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

        hook_thread = multiprocessing.Process(target=other_thread_fn, args=(), name='AcquisitionHook') if multiprocessing\
            else threading.Thread(target=other_thread_fn, args=(), name='AcquisitionHook')
        hook_thread.start()

        hook_connected_evt.wait()  # wait for push/pull sockets to connect

    def _start_processor(self, processor, process_fn, event_queue, multiprocessing):
        # this must start first
        processor.start_pull()

        sockets_connected_evt = multiprocessing.Event() if multiprocessing else threading.Event()

        pull_port = processor.get_pull_port()
        push_port = processor.get_push_port()
        def other_thread_fn():
            bridge = PygellanBridge()
            # setattr(process_fn, 'bridge', bridge)
            push_socket = bridge.connect_push(pull_port)
            pull_socket = bridge.connect_pull(push_port)
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

        self.processor_thread = multiprocessing.Process(target=other_thread_fn, args=(),  name='ImageProcessor'
                        ) if multiprocessing else threading.Thread(target=other_thread_fn, args=(),  name='ImageProcessor')
        self.processor_thread.start()

        sockets_connected_evt.wait()  # wait for push/pull sockets to connect
        processor.start_push()

def z_stack(start, stop, step):
    event_list = []
    for i, z in enumerate(np.arange(start, stop, step)):
        event = {}
        event['axes'] = {}
        event['axes']['z'] = i
        event['z'] = float(z)
        event['channel'] = {'group': 'Channel', 'config': 'FITC'}
        event['exposure'] = 100
        event_list.append(event)
    return event_list

def other_channel(existing_axes):
    event_list = []
    event = {}
    event['axes'] = existing_axes
    event['channel'] = {'group': 'Channel', 'config': 'DAPI'}
    event['exposure'] = 10
    event_list.append(event)
    return event_list

# def led_stack():
#     event_list = []
#     for i, l in enumerate(np.arange(100)):
#         event = {}
#         event['axes'] = {'led': i}
#         event['channel'] = {'group': 'Channel', 'config': 'DAPI'}
#         event['exposure'] = 10
#         event_list.append(event)
#     return event_list

events = z_stack(0, 100, 1)
first = events[0]
rest = events[1:]

#Version 1:
def hook_fn(event):
    return event

#Version 2:
def hook_fn(event, bridge, event_queue):
    return event

#Version 1:
def img_process_fn(image, metadata):
    image[250:350, 100:300] = np.random.randint(0, 4999)
    return image, metadata

#Version 2:
def img_process_fn_events(image, metadata, bridge, event_queue):
    #some operation on image to check for particular pattern in pixels
    if np.random.randint(2):
        event_queue.put(other_channel(metadata['AxesPositions']))
    if (len(rest) > 0):
        event_queue.put(rest.pop(0))
    else:
        event_queue.put(None)
    return image, metadata

acq = Acquisition('/Users/henrypinkard/megllandump', 'pythonacqtest',
                  channel_group='Channel', image_process_fn=img_process_fn_events,
                 post_hardware_hook_fn=hook_fn)

acq.acquire(first)




