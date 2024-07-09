from pycromanager import ZMQRemoteMMCoreJ, JavaClass
from threading import Thread

### Pass object to a different thread
core = ZMQRemoteMMCoreJ(debug=False)
def other_thread(core):
    cache = core.get_system_state_cache()
    print(cache)
Thread(target=other_thread, args=(core,) ).start()

core = None

### Create an object and a child object on a new socket

core = ZMQRemoteMMCoreJ(debug=False)
core.get_system_state_cache(new)


### Access a static java class
c = JavaClass("java.util.Arrays")
pass
