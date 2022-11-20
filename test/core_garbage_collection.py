from pycromanager import Core
import gc


core = Core(debug=False, convert_camel_case=False)

core.startSequenceAcquisition(500, 0., True)

while core.getRemainingImageCount() > 0 or core.isSequenceRunning():
    if core.getRemainingImageCount() > 0:
        tagged = core.popNextTaggedImage()
        gc.collect()
    else:
        core.sleep(5)

pass