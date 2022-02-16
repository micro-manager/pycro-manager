from pycromanager import Bridge
import threading
from psygnal import Signal

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



class CMMCoreSignaler:

    # native MMCore callback events
    propertiesChanged = Signal()
    propertyChanged = Signal(str, str, str)
    channelGroupChanged = Signal(str)
    configGroupChanged = Signal(str, str)
    configSet = Signal(str, str)
    systemConfigurationLoaded = Signal()
    pixelSizeChanged = Signal(float)
    pixelSizeAffineChanged = Signal(float, float, float, float, float, float)
    stagePositionChanged = Signal(str, float)
    XYStagePositionChanged = Signal(str, float, float)
    exposureChanged = Signal(str, float)
    SLMExposureChanged = Signal(str, float)

    # this signal will emit a single string
    value_changed = Signal(str)

    def __init__(self, bridge_port=Bridge.DEFAULT_PORT):
        self._value = None
        self._closed = False

        self._thread = threading.Thread(
            target=_callback_recieving_fn,
            name="CoreCallback",
            args=(bridge_port, self),
        )
        self._thread.start()

    def set_value(self, value):
        function_name = value['name']
        function_args = value['arguments']
        print(function_name, function_args)
        #TODO call using relfection and function name
        #     self.propertiesChanged.emit(self._value)

    def close(self):
        self._closed = True
        self._thread.join()

