from pycromanager import Core
import numpy as np
import time

core = Core()

camera_name = core.get_camera_device()

#trigger mode
core.set_trigger_mode(camera_name, 'FrameStart', True)
print(core.get_trigger_mode(camera_name, 'FrameStart'))
core.set_trigger_mode(camera_name, 'FrameStart', False)
print(core.get_trigger_mode(camera_name, 'FrameStart'))

# trigger source
core.set_trigger_source(camera_name, 'FrameStart', 'Software')
print(core.get_trigger_source(camera_name, 'FrameStart'))
core.set_trigger_source(camera_name, 'FrameStart', 'Hardware')
print(core.get_trigger_source(camera_name, 'FrameStart'))


# trigger activation
core.set_trigger_activation(camera_name, 'FrameStart', 'FallingEdge')
print(core.get_trigger_activation(camera_name, 'FrameStart'))
core.set_trigger_activation(camera_name, 'FrameStart', 'RisingEdge')
print(core.get_trigger_activation(camera_name, 'FrameStart'))

# trigger delay
core.set_trigger_delay(camera_name, 'FrameStart', 300)
print(core.get_trigger_delay(camera_name, 'FrameStart'))
core.set_trigger_delay(camera_name, 'FrameStart', 0)
print(core.get_trigger_delay(camera_name, 'FrameStart'))



