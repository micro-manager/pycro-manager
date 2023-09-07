import threading
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification

def _axes_to_key(axes):
    """ Turn axes into a hashable key """
    return frozenset(axes.items())

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
        if notification.phase == AcqNotification.Acquisition.ACQ_EVENTS_FINISHED or \
            notification.phase == AcqNotification.Image.DATA_SINK_FINISHED:
            return # ignore for now...
        if isinstance(notification.id, list):
            keys = [_axes_to_key(ax) for ax in notification.id]
        else:
            keys = [_axes_to_key(notification.id)]
        # check if any keys are present in the notification_recieved dict
        if not any([key in self._notification_recieved.keys() for key in keys]):
            return # ignore notifications that aren't relevant to this future
        for key in keys:
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
        if isinstance(axes, list):
            keys = [_axes_to_key(ax) for ax in axes]
        else:
            keys = [_axes_to_key(axes)]
        for key in keys:
            with self._condition:
                while not self._notification_recieved[key][AcqNotification.Image.IMAGE_SAVED]:
                    self._condition.wait()
        if return_image:
            if isinstance(axes, list):
                return [self._acq.get_dataset().read_image(**ax) for ax in axes]
            else:
                return self._acq.get_dataset().read_image(**axes)


