"""
This example shows how to do basic micro-manager introspection using
pycro-manager.
"""

from pycromanager import Core


# Connect to MM.
core = Core()


# Current configuration.
def current_config():
    devices = core.get_loaded_devices()
    for i in range(devices.size()):
        devstr = devices.get(i)
        print("Device: ", devstr)

        pnames = core.get_device_property_names(devstr)

        for i in range(pnames.size()):
            pname = pnames.get(i)
            pvalue = core.get_property(devstr, pname)
            ptype = core.get_property_type(devstr, pname).to_string()
            print(f"  {devstr}-{pname} '{pvalue}' {ptype}")
        print()
        
        
# Current ROI.
def current_roi():
    roi = core.get_roi()
    print(f"x: {roi.x}, y: {roi.y}, width: {roi.width}, height: {roi.height}")


# Properties of a JAVA object.
def pyjavaz_props():
    roi = core.get_roi()
    print(dir(roi))

    
print("Example JAVA object properties:")
pyjavaz_props()
print()

print("Getting the current ROI:")
current_roi()
print()

print("Getting the current configuration:")
current_config()
print()
