
EVENT_GENERATION_HOOK = 0
# This hook runs before changes to the hardware (corresponding to the instructions in the
# event) are made
BEFORE_HARDWARE_HOOK = 1
# This hook runs after all changes to the hardware except dor setting th Z drive have been
# made.  This is useful for things such as autofocus.
BEFORE_Z_DRIVE_HOOK = 2
# This hook runs after changes to the hardware took place, but before camera exposure
# (either a snap or a sequence) is started
AFTER_HARDWARE_HOOK = 3
# Hook runs after the camera sequence acquisition has started. This can be used for
# external triggering of the camera
AFTER_CAMERA_HOOK = 4
# Hook runs after the camera exposure ended (when possible, before readout of the camera
# and availability of the images in memory).
AFTER_EXPOSURE_HOOK = 5