import json
import warnings


class AcqNotification:

    class Acquisition:
        ACQ_STARTED = "acq_started"
        ACQ_EVENTS_FINISHED = "acq_events_finished"

        @staticmethod
        def to_string():
            return "global"

    class Hardware:
        PRE_HARDWARE = "pre_hardware"
        PRE_Z_DRIVE = "pre_z_drive"
        POST_HARDWARE = "post_hardware"

        @staticmethod
        def to_string():
            return "hardware"

    class Camera:
        PRE_SEQUENCE_STARTED = "pre_sequence_started"
        POST_SEQUENCE_STOPPED = "post_sequence_stopped"
        PRE_SNAP = "pre_snap"
        POST_SNAP = "post_snap"

        @staticmethod
        def to_string():
            return "camera"

    class Image:
        IMAGE_SAVED = "image_saved"
        DATA_SINK_FINISHED = "data_sink_finished"

        @staticmethod
        def to_string():
            return "image"

    def __init__(self, type, payload, milestone=None):
        if type == AcqNotification.Acquisition or type == AcqNotification.Acquisition.to_string():
            self.type = AcqNotification.Acquisition
            self.payload = payload
            self.milestone = milestone
        elif (type == AcqNotification.Image or type == AcqNotification.Image.to_string()) and \
              milestone == AcqNotification.Image.DATA_SINK_FINISHED:
            self.type = AcqNotification.Image
            self.payload = payload
            self.milestone = milestone
        elif milestone in [AcqNotification.Camera.PRE_SNAP, AcqNotification.Camera.POST_SNAP,
                     AcqNotification.Camera.PRE_SEQUENCE_STARTED, AcqNotification.Camera.POST_SEQUENCE_STOPPED]:
            self.type = AcqNotification.Camera
            self.payload = json.loads(payload) if isinstance(payload, str) else payload # convert from '{'time': 5}' to {'time': 5}
        elif milestone in [AcqNotification.Hardware.PRE_HARDWARE, AcqNotification.Hardware.PRE_Z_DRIVE, AcqNotification.Hardware.POST_HARDWARE]:
            self.type = AcqNotification.Hardware
            self.payload = json.loads(payload) if isinstance(payload, str) else payload # convert from '{'time': 5}' to {'time': 5}
        elif milestone == AcqNotification.Image.IMAGE_SAVED:
            self.type = AcqNotification.Image
            self.payload = payload
        else:
            warnings.warn(f"Unknown notification type {type} with milestone {milestone}")
        self.milestone = milestone


    @staticmethod
    def create_acq_events_finished_notification():
       return AcqNotification(AcqNotification.Acquisition, None, AcqNotification.Acquisition.ACQ_EVENTS_FINISHED)

    @staticmethod
    def create_acq_started_notification():
        return AcqNotification(AcqNotification.Acquisition, None, AcqNotification.Acquisition.ACQ_STARTED)

    @staticmethod
    def create_data_sink_finished_notification():
        return AcqNotification(AcqNotification.Image, None, AcqNotification.Image.DATA_SINK_FINISHED)

    @staticmethod
    def create_image_saved_notification(image_descriptor):
        return AcqNotification(AcqNotification.Image, image_descriptor, AcqNotification.Image.IMAGE_SAVED)

    def __repr__(self):
        json = self.to_json()
        return f"AcqNotification({json})"

    def to_json(self):
        n = {}
        n['type'] = self.type
        n['milestone'] = self.milestone
        if self.payload:
            n['payload'] = self.payload
        return n

    @staticmethod
    def from_json(json):
        return AcqNotification(json['type'],
                               json['payload'] if 'payload' in json else None,
                               json['milestone'] if 'milestone' in json else None)

    def is_acquisition_finished_notification(self):
        return self.milestone == AcqNotification.Acquisition.ACQ_EVENTS_FINISHED

    def is_data_sink_finished_notification(self):
        return self.milestone == AcqNotification.Image.DATA_SINK_FINISHED

    def is_image_saved_notification(self):
        return self.milestone == AcqNotification.Image.IMAGE_SAVED
