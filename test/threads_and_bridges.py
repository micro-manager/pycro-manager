from pycromanager.mm_java_classes import Core, JavaObject, JavaClass
from pycromanager import _Bridge
import gc
import threading

def new_b():
    core = Core()

for i in range(100):
    # core = Dummy()
    core = Core()
    core2 = Core()

    threading.Thread(target=new_b).start()

    core = None
    core2 = None


    # del core
    gc.collect()
    pass

# with Bridge() as b:
#     core = b.get_core()
#     core = None

a = JavaObject('java.util.ArrayList')


