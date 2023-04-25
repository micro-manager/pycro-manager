from pycromanager import Core
import numpy as np
import time

from arduino_triggering import TriggerTester

### Setup
trigger_arduino = TriggerTester('COM3')

core = Core()
core.set_exposure(500)
camera_name = core.get_camera_device()

trigger_arduino.send_trigger(5)


def wait_and_pop_image():
    while core.get_remaining_image_count() == 0:
        time.sleep(0.01)
    return core.pop_next_image()