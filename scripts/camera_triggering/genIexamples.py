"""
This example shows how to use pycromanager to interact with the micro-manager core.
Aside from the setup section, each following section can be run independently
"""
from pycromanager import Core
import numpy as np
import time

from arduino_triggering import TriggerTester

### Setup
trigger_arduino = TriggerTester('COM3')

core = Core()
core.set_exposure(500)
camera_name = core.get_camera_device()

def wait_and_pop_image():
    while core.get_remaining_image_count() == 0:
        time.sleep(0.01)
    return core.pop_next_image()


def clear_triggers():
    core.set_trigger_mode(camera_name, 'FrameStart', False)
    core.set_trigger_mode(camera_name, 'AcquisitionStart', False)

def live_mode_no_triggers():
    ### Live mode with no triggering
    # TODO: turn all triggers off
    # Continuous acquisition when the camera is in its reset state. */
    # AcquisitionMode = Continuous;
    # AcquisitionStart();
    # ...
    # AcquisitionStop();
    clear_triggers()
    core.arm_acquisition(camera_name)
    core.start_acquisition(camera_name)
    # acquire 5 images and make sure they're not empty
    for i in range(5):
        image = wait_and_pop_image()
        print(np.mean(image))
    core.stop_acquisition(camera_name)

def snap_with_hardware_trigger():
    # Snap with a external trigger
    # /* Single Frame acquisition in Hardware trigger mode using the external I/O Line 3. */
    # AcquisitionMode = SingleFrame;
    # TriggerSelector = FrameStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # AcquisitionStart();
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Line1')
    core.set_trigger_activation(camera_name, 'FrameStart', 'RisingEdge')
    core.arm_acquisition(camera_name, 1)
    core.start_acquisition(camera_name)
    trigger_arduino.send_trigger(5)
    image = wait_and_pop_image()
    print(np.mean(image))

def snap_with_software_trigger():
    # Snap with a software trigger
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Software')
    core.arm_acquisition(camera_name, 1)
    core.start_acquisition(camera_name)
    core.send_software_trigger(camera_name, 'FrameStart')
    image = wait_and_pop_image()
    print(np.mean(image))


def multi_frame_software_trigger_delay():
    # /* Multi-Frame acquisition started by a single Software trigger delayed by 1 millisecond.
    # The Trigger starts the whole sequence acquisition.
    # AcquisitionMode = MultiFrame;
    # AcquisitionFrameCount = 20;
    # TriggerSelector = AcquisitionStart;
    # TriggerMode = On;
    # TriggerSource = Software;
    # TriggerDelay = 1000;
    # ExposureMode = Timed;
    # ExposureTime = 500;
    # AcquisitionStart();
    # TriggerSoftware();
    num_frames = 20
    clear_triggers()
    core.set_trigger_mode(camera_name, 'AcquisitionStart', True)
    core.set_trigger_source(camera_name, 'AcquisitionStart', 'Software')
    core.set_trigger_delay(camera_name, 'AcquisitionStart', 1000)
    core.set_exposure_mode(camera_name, 'Timed')
    core.set_exposure(camera_name, 500)
    core.arm_acquisition(camera_name, num_frames)
    core.start_acquisition(camera_name)
    for i in range(num_frames):
        core.send_software_trigger(camera_name, 'AcquisitionStart')
        image = wait_and_pop_image()
        print(np.mean(image))


def live_mode_hardware_trigger():
    # /* Continuous acquisition in Hardware trigger mode. The Frame triggers are Rising Edge signals
    # coming from the physical Line 2. The Exposure time is 500us. An exposure end event is also
    # sent to the Host application after the exposure of each frame to signal that the inspected part
    # can be moved. The timestamp of the event is also read.
    # */
    # AcquisitionMode = Continuous;
    # TriggerSelector = FrameStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # TriggerSource = Line2; # We use "Line1"
    # ExposureMode = Timed;
    # ExposureTime = 500;
    # Register(Camera.EventExposureEnd, CallbackDataObject, CallbackFunctionPtr)
    # EventSelector = ExposureEnd;
    # EventNotification = On;
    # AcquisitionStart();
    # ...
    # // In the callback of the ExposureEnd event, get the event timestamp:
    # Timestamp = EventExposureEndTimestamp;
    # ...
    # AcquisitionStop();
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Line1')
    core.set_trigger_activation(camera_name, 'FrameStart', 'RisingEdge')
    core.set_exposure_mode(camera_name, 'Timed')
    core.set_exposure(camera_name, 500)
    core.arm_acquisition(camera_name)
    core.start_acquisition(camera_name)
    # TODO: events
    # Register(Camera.EventExposureEnd, CallbackDataObject, CallbackFunctionPtr)
    # EventSelector = ExposureEnd;
    # EventNotification = On;
    for i in range(5):
        trigger_arduino.send_trigger(10)
        image = wait_and_pop_image()
        print(np.mean(image))
    core.stop_acquisition(camera_name)


def hardware_trigger_plus_output_ttl():
    # TODO
    # /* Multi-Frame acquisition with each frame triggered by a Hardware trigger on Line 1.
    # A negative pulse of the exposure signal duration (500us) is also sent to the physical
    # output line 2 to activate a light during the exposure time of each frame. The end of
    # the sequence capture is signalled to the host with an acquisition end event.
    # */
    # AcquisitionMode = MultiFrame;
    # AcquisitionFrameCount = 20;
    # TriggerSelector = FrameStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # TriggerSource = Line1;
    # ExposureMode = Timed;
    # ExposureTime = 500;
    # LineSelector = Line2;
    # LineMode = Output;
    # LineInverter = True;
    # LineSource = ExposureActive
    # Register(Camera.EventAcquisitionEnd,CallbackDataObject,CallbackFunctionPtr)
    # EventSelector = AcquisitionEnd;
    # EventNotification = On;
    # AcquisitionStart();
    pass


def multiple_bursts_hardware_trigger():
    # /* Continuous Acquisition of frames in bursts of 10 frames. Each burst is triggered by a
    # Hardware trigger on Line 1. The end of each burst capture is signalled to the host with a
    # FrameBurstEnd event.
    # */
    # AcquisitionMode = Continuous;
    # AcquisitionBurstFrameCount = 10;
    # TriggerSelector = FrameBurstStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # TriggerSource = Line1;
    # TODO events
    # Register(Camera.EventFrameBurstEnd,CallbackDataObject,CallbackFunctionPtr)
    # EventSelector = FrameBurstEnd;
    # EventNotification = On;
    # AcquisitionStart();
    # ...
    # // In the callback of the end of burst event, get the event timestamp:
    # Timestamp = EventExposureEndTimestamp;
    # ...
    # AcquisitionStop();
    pass
    burst_size = 10
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameBurstStart', True)
    core.set_trigger_source(camera_name, 'FrameBurstStart', 'Line1')
    core.set_trigger_activation(camera_name, 'FrameBurstStart', 'RisingEdge')
    core.set_exposure_mode(camera_name, 'Timed')
    core.set_exposure(camera_name, 100)
    core.set_burst_frame_count(camera_name, burst_size)
    core.arm_acquisition(camera_name) # continuous bursts
    core.start_acquisition(camera_name)
    for i in range(6):
        trigger_arduino.send_trigger(5)
        for j in range(burst_size):
            image = wait_and_pop_image()
            print(np.mean(image))


def live_mode_with_strobe_trigger():
    # /* Frame Scan continuous acquisition with Hardware Frame trigger and the
    # Exposure duration controlled by the Trigger pulse width.
    # */
    # AcquisitionMode = Continuous;
    # TriggerSelector = FrameStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # TriggerSource = Line1;
    # ExposureMode = TriggerWidth;
    # AcquisitionStart();
    # ...
    # AcquisitionStop();
    pass

def live_mode_stop_and_start_exposure_triggers():
    # /* Frame Scan continuous acquisition with 1 Hardware trigger controlling
    # the start of the acquisition and 2 others harware triggers to start and stop
    # the exposure of each frame.
    # */
    # AcquisitionMode = Continuous;
    # TriggerSelector = AcquisitionStart;
    # TriggerMode = On;
    # TriggerSource = Line1;
    # ExposureMode = TriggerControlled;
    # TriggerSelector = ExposureStart;
    # TriggerMode = On;
    # TriggerSource = Line3;
    # TriggerSelector = ExposureStop;
    # TriggerMode = On;
    # TriggerSource = Line4;
    # AcquisitionStart();
    # ...
    # AcquisitionStop();
    pass


def finite_series_bursts():
    # /* Multi-Frame Acquisition of 50 frames in 5 bursts of 10 frames. Each burst is triggered by a
    # Hardware trigger on Line 1.
    # */
    # AcquisitionMode = MultiFrame;
    # AcquisitionFrameCount = 50;
    # AcquisitionBurstFrameCount = 10;
    # TriggerSelector = FrameBurstStart;
    # TriggerMode = On;
    # TriggerActivation = RisingEdge;
    # TriggerSource = Line1;
    # AcquisitionStart();
    pass


def abort_continuous_hardware_triggered():
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Line1')
    core.set_trigger_activation(camera_name, 'FrameStart', 'RisingEdge')
    core.set_exposure_mode(camera_name, 'Timed')
    core.set_exposure(camera_name, 500)
    core.arm_acquisition(camera_name)
    core.start_acquisition(camera_name)
    for i in range(2):
        trigger_arduino.send_trigger(10)
        image = wait_and_pop_image()
        print(np.mean(image))
    core.abort_acquisition(camera_name)


def acquisition_status_software_trigger():
    clear_triggers()
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Software')
    core.arm_acquisition(camera_name, 1)
    core.start_acquisition(camera_name)
    core.send_software_trigger(camera_name, 'FrameStart')
    image = wait_and_pop_image()
    print(np.mean(image))

def test_acq_status_software_trigger():
    clear_triggers()
    core.set_exposure(camera_name, 500)
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Software')
    core.arm_acquisition(camera_name, 1)
    core.start_acquisition(camera_name)
    print('Status before trigger (expect True): ', core.get_acquisition_status(camera_name, "FrameTriggerWait"))
    core.send_software_trigger(camera_name, 'FrameStart')
    print('Status after trigger (expect False): ', core.get_acquisition_status(camera_name, "FrameTriggerWait"))
    image = wait_and_pop_image()
    print('Status after image (expect False): ', core.get_acquisition_status(camera_name, "FrameTriggerWait"))


def test_acq_status_hardware_trigger():
    clear_triggers()
    core.set_exposure(camera_name, 500)
    core.set_trigger_mode(camera_name, 'FrameStart', True)
    core.set_trigger_source(camera_name, 'FrameStart', 'Line1')
    core.set_line_as_output(camera_name, "Line2", True)
    core.set_output_line_source(camera_name, "Line2", "AcquisitionActive")
    core.arm_acquisition(camera_name, 1)
    print('Status before acq (expect False): ', core.get_line_status(camera_name, "Line2"))
    core.start_acquisition(camera_name)
    print('Status before trigger (expect True): ', core.get_line_status(camera_name, "Line2"))
    trigger_arduino.send_trigger(5)
    image = wait_and_pop_image()
    print('Status after readount (expect False): ', core.get_line_status(camera_name, "Line2"))


# TODO change to another 2 triggers (AcquisitionStart and FrameStart?)
# /* Line Scan continuous acquisition with Hardware Frame and Line trigger. */
# AcquisitionMode = Continuous;
# TriggerSelector = FrameStart;
# TriggerMode = On;
# TriggerActivation = RisingEdge;
# TriggerSource = Line1;
# TriggerSelector = LineStart;
# TriggerMode = On;
# TriggerActivation = RisingEdge;
# TriggerSource = Line2;
# AcquisitionStart();
# ...
# AcquisitionStop();


# live_mode_no_triggers()
# snap_with_software_trigger()
# snap_with_hardware_trigger()
# multi_frame_software_trigger_delay()
# live_mode_hardware_trigger()
# multiple_bursts_hardware_trigger()
# abort_continuous_hardware_triggered()
# test_acq_status_software_trigger()
test_acq_status_hardware_trigger()


# TODO
# live_mode_with_strobe_trigger()
# live_mode_stop_and_start_exposure_triggers()
# finite_series_bursts()
# hardware_trigger_plus_output_ttl()




