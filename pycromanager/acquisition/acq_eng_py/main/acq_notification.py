import json

class AcqNotification:

    class Acquisition:
        ACQ_STARTED = "acq_started"
        ACQ_EVENTS_FINISHED = "acq_events_finished"

        @staticmethod
        def to_string():
            return "global"

    class Hardware:
        PRE_HARDWARE = "pre_hardware"
        POST_HARDWARE = "post_hardware"

        @staticmethod
        def to_string():
            return "hardware"

    class Camera:
        PRE_SEQUENCE_STARTED = "pre_sequence_started"
        PRE_SNAP = "pre_snap"
        POST_EXPOSURE = "post_exposure"

        @staticmethod
        def to_string():
            return "camera"

    class Image:
        IMAGE_SAVED = "image_saved"
        DATA_SINK_FINISHED = "data_sink_finished"

        @staticmethod
        def to_string():
            return "image"

    def __init__(self, type, id, phase=None):
        if type == AcqNotification.Acquisition.to_string():
            self.type = AcqNotification.Acquisition
            self.id = id
            self.phase = phase
        elif type == AcqNotification.Image.to_string() and phase == AcqNotification.Image.DATA_SINK_FINISHED:
            self.type = AcqNotification.Image
            self.id = id
            self.phase = phase
        elif phase in [AcqNotification.Camera.PRE_SNAP, AcqNotification.Camera.POST_EXPOSURE,
                     AcqNotification.Camera.PRE_SEQUENCE_STARTED]:
            self.type = AcqNotification.Camera
            self.id = json.loads(id)
        elif phase in [AcqNotification.Hardware.PRE_HARDWARE, AcqNotification.Hardware.POST_HARDWARE]:
            self.type = AcqNotification.Hardware
            self.id = json.loads(id)
        elif phase == AcqNotification.Image.IMAGE_SAVED:
            self.type = AcqNotification.Image
            self.id = id
        else:
            raise ValueError("Unknown phase")
        self.phase = phase


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

    def to_json(self):
        n = {}
        n['type'] = self.type
        n['phase'] = self.phase
        if self.id:
            n['id'] = self.id
        return n

    @staticmethod
    def from_json(json):
        return AcqNotification(json['type'],
                               json['id'] if 'id' in json else None,
                               json['phase'] if 'phase' in json else None)

    def is_acquisition_finished_notification(self):
        return self.phase == AcqNotification.Acquisition.ACQ_EVENTS_FINISHED

    def is_data_sink_finished_notification(self):
        return self.phase == AcqNotification.Image.DATA_SINK_FINISHED

    def is_image_saved_notification(self):
        return self.phase == AcqNotification.Image.IMAGE_SAVED
