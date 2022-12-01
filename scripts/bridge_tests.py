from pycromanager import Core, JavaClass
from threading import Thread

### Pass object to a different thread
core = Core(debug=False)
def other_thread(core):
    cache = core.get_system_state_cache()
    print(cache)
Thread(target=other_thread, args=(core,) ).start()

core = None

### Create an object and a child object on a new socket

core = Core(debug=False)
core.get_system_state_cache(new)


### Access a static java class
c = JavaClass("java.util.Arrays")
pass
