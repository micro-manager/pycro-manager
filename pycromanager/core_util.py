from pycromanager.zmq import Bridge
import threading

def _callback_recieving_fn(bridge_port, core_callback):

    with Bridge(port=bridge_port) as bridge:
        callback_java = bridge.construct_java_object('org.micromanager.remote.RemoteCoreCallback',
                                                     args=(bridge.get_core(),))
        port = callback_java.get_push_port()
        pull_socket = bridge._connect_pull(port)
        callback_java.start_push()
        while True:
            message = pull_socket.receive(timeout=100)
            if message is not None:
                core_callback.set_value(message)
            if core_callback._closed:
                callback_java.shutdown()
                break


class CoreCallback:
    """
    A class for recieving callbacks from the core, which are mostly used
    for the case where some hardware has changed
    See (https://github.com/micro-manager/mmCoreAndDevices/blob/main/MMCore/CoreCallback.cpp)
    """
    def __init__(self, callback_fn=None, bridge_port=Bridge.DEFAULT_PORT):
        self._closed = False
        self._thread = threading.Thread(
            target=_callback_recieving_fn,
            name="CoreCallback",
            args=(bridge_port, self),
        )
        self.callback_fn = callback_fn
        self._thread.start()

    def set_value(self, value):
        function_name = value['name']
        function_args = value['arguments'] if 'arguments' in value else tuple()

        print(function_name, function_args)
        if self.callback_fn is not None:
            self.callback_fn(function_name, *function_args)

    def close(self):
        self._closed = True
        self._thread.join()

