from pycromanager.mm_java_classes import ZMQRemoteMMCoreJ, JavaObject, JavaClass
from pycromanager import _Bridge
import gc
import threading

def new_b():
    core = ZMQRemoteMMCoreJ()

for i in range(100):
    # core = Dummy()
    core = ZMQRemoteMMCoreJ()
    core2 = ZMQRemoteMMCoreJ()

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


