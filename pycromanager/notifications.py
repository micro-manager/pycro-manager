import threading

class AcqNotification:

    class Global:
        ACQ_STARTED = "acq_started"
        ACQ_FINISHED = "acq_finished"

    class Hardware:
        PRE_HARDWARE = "pre_hardware"
        POST_HARDWARE = "post_hardware"

    class Camera:
        PRE_SEQUENCE_STARTED = "pre_sequence_started"
        PRE_SNAP = "pre_snap"
        POST_EXPOSURE = "post_exposure"

    class Image:
        IMAGE_SAVED = "image_saved"

    def __init__(self, type, axes, phase=None):
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
        self.axes = axes

    @staticmethod
    def make_image_saved_notification(axes):
        return AcqNotification(AcqNotification.Image, axes, AcqNotification.Image.IMAGE_SAVED)

    def to_json(self):
        return {
            'type': self.type,
            'phase': self.phase,
            'axes': self.axes,
        }

    @staticmethod
    def from_json(json):
        return AcqNotification(json['type'], json['axes'] if 'axes' in json else None,
                               json['phase'] if 'phase' in json else None)


def _axes_to_key(axes_or_axes_list):
    """ Turn axes into a hashable key """
    return frozenset(axes_or_axes_list.items())


class AcquisitionFuture:

    def __init__(self, acq, axes_or_axes_list):
        """
        :param event_or_events: a single event (dictionary) or a list of events
        """
        self._acq = acq
        self._condition = threading.Condition()
        self._notification_recieved = {}
        if isinstance(axes_or_axes_list, dict):
            axes_or_axes_list = [axes_or_axes_list]
        for axes in axes_or_axes_list:
            # single event
            # TODO maybe unify snap and sequence cause this is confusing
            self._notification_recieved[_axes_to_key(axes)] = {
                AcqNotification.Hardware.PRE_HARDWARE: False,
                AcqNotification.Hardware.POST_HARDWARE: False,

                AcqNotification.Camera.PRE_SNAP: False,
                AcqNotification.Camera.PRE_SEQUENCE_STARTED: False,
                AcqNotification.Camera.POST_EXPOSURE: False,

                AcqNotification.Image.IMAGE_SAVED: False,
            }


    def _notify(self, notification):
        """
        Called by the internal notification dispatcher in order so that it can check off that the notification was
        received. Want to store this, rather than just waiting around for it, in case the await methods are called
        after the notification has already been sent.
        """
        if notification.type == AcqNotification.Global.ACQ_FINISHED:
            return # ignore for now...
        key = _axes_to_key(notification.axes)
        if key not in self._notification_recieved.keys():
            return # ignore notifications that aren't relevant to this future
        self._notification_recieved[key][notification.phase] = True
        with self._condition:
            self._condition.notify_all()

    def await_execution(self, axes, phase):
        key = _axes_to_key(axes)
        if key not in self._notification_recieved.keys() or phase not in self._notification_recieved[key].keys():
            notification = AcqNotification(None, axes, phase)
            raise ValueError("this future is not expecting a notification for: " + str(notification.to_json()))
        with self._condition:
            while not self._notification_recieved[key][phase]:
                self._condition.wait()

    def await_image_saved(self, axes, return_image=False):
        key = _axes_to_key(axes)
        with self._condition:
            while not self._notification_recieved[key][AcqNotification.Image.IMAGE_SAVED]:
                self._condition.wait()
        if return_image:
            return self._acq.get_dataset().read_image(**axes)


