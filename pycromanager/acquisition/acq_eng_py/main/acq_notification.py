class AcqNotification:

    class Acquisition:
        ACQ_STARTED = "acq_started"
        ACQ_EVENTS_FINISHED = "acq_events_finished"

        @staticmethod
        def to_string():
            return "Global"

    class Hardware:
        PRE_HARDWARE = "pre_hardware"
        POST_HARDWARE = "post_hardware"

        @staticmethod
        def to_string():
            return "Hardware"

    class Camera:
        PRE_SEQUENCE_STARTED = "pre_sequence_started"
        PRE_SNAP = "pre_snap"
        POST_EXPOSURE = "post_exposure"

        @staticmethod
        def to_string():
            return "Camera"

    class Image:
        IMAGE_SAVED = "image_saved"
        DATA_SINK_FINISHED = "data_sink_finished"

        @staticmethod
        def to_string():
            return "Image"

    def __init__(self, type, id, phase=None):
        if type is None:
            # then figure it out based on the phase
            if phase in [AcqNotification.Camera.PRE_SNAP, AcqNotification.Camera.POST_EXPOSURE,
                         AcqNotification.Camera.PRE_SEQUENCE_STARTED]:
                type = AcqNotification.Camera
            elif phase in [AcqNotification.Hardware.PRE_HARDWARE, AcqNotification.Hardware.POST_HARDWARE]:
                type = AcqNotification.Hardware
            elif phase == AcqNotification.Image.IMAGE_SAVED:
                type = AcqNotification.Image
            else:
                raise ValueError("Unknown phase")
        self.type = type
        self.phase = phase
        self.id = id


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
