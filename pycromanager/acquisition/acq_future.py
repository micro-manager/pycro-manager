import threading
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification
from types import GeneratorType

def _axes_to_key(axes):
    """ Turn axes into a hashable key """
    return None if axes is None else frozenset(axes.items())

class AcquisitionFuture:

    def __init__(self, acq, axes_or_axes_list=None):
        """
        :param axes_or_axes_list: a single axes (dictionary) or a list of axes
        """
        self._acq = acq
        self._condition = threading.Condition()
        self._notification_recieved = {}
        self._generator_events = axes_or_axes_list is None
        if not self._generator_events:
            self._add_notifications(axes_or_axes_list)
        self._last_notification = None

    def _add_notifications(self, axes_or_axes_list):
        if isinstance(axes_or_axes_list, dict):
            axes_or_axes_list = [axes_or_axes_list]
        for axes in axes_or_axes_list:
            # TODO maybe unify snap and sequence cause this is confusing
            self._notification_recieved[_axes_to_key(axes)] = {
                AcqNotification.Hardware.PRE_HARDWARE: False,
                AcqNotification.Hardware.PRE_Z_DRIVE: False,
                AcqNotification.Hardware.POST_HARDWARE: False,

                AcqNotification.Camera.PRE_SNAP: False,
                AcqNotification.Camera.PRE_SEQUENCE_STARTED: False,
                AcqNotification.Camera.POST_SNAP: False,
                AcqNotification.Camera.POST_SEQUENCE_STOPPED: False,

                AcqNotification.Image.IMAGE_SAVED: False,
            }


    def _notify(self, notification):
        """
        Called by the internal notification dispatcher in order so that it can check off that the notification was
        received. Want to store this, rather than just waiting around for it, in case the await methods are called
        after the notification has already been sent.
        """
        if notification.milestone == AcqNotification.Acquisition.ACQ_EVENTS_FINISHED or \
            notification.milestone == AcqNotification.Image.DATA_SINK_FINISHED:
            with self._condition:
                self._last_notification = notification
                self._condition.notify_all()
            return
        if isinstance(notification.payload, list):
            keys = [_axes_to_key(ax) for ax in notification.payload]
        else:
            keys = [_axes_to_key(notification.payload)]
        # check if any keys are present in the notification_recieved dict
        if not any([key in self._notification_recieved.keys() for key in keys]):
            return # ignore notifications that aren't relevant to this future
        for key in keys:
            self._notification_recieved[key][notification.milestone] = True
        with self._condition:
            self._last_notification = notification
            self._condition.notify_all()

    def _monitor_axes(self, axes_or_axes_list):
        """
        In the case where the acquisition future is constructed for a Generator, the events to be monitored
        are not known until the generator is run. If user code awaits for an event and that event has already
        passed, the future must be able to check if the event has already passed and return immediately.
        So this function is called by the generator as events are created to add them to the list of events to
        keep track of.

        :param axes_or_axes_list: the axes of the event
        """
        if self._generator_events:
            self._add_notifications(axes_or_axes_list)
        else:
            raise ValueError("This future was not constructed with a generator")

    def await_execution(self, milestone, axes=None):
        """
        Block until the given milestone is executed for the given axes

        Parameters
        ----------
        axes: dict
            the axes to wait for
        milestone:
            the milestone to wait for (e.g. AcqNotification.Hardware.POST_HARDWARE)
        """
        key = _axes_to_key(axes)
        if not self._generator_events:
            if key not in self._notification_recieved.keys() or milestone not in self._notification_recieved[key].keys():
                notification = AcqNotification(None, axes, milestone)
                raise ValueError("this future is not expecting a notification for: " + str(notification.to_json()))
        with self._condition:
            while not self._notification_recieved[key][milestone]:
                self._condition.wait()

    def await_image_saved(self, axes=None, return_image=True, return_metadata=False):
        """
        Block until the image with the given axes is saved. Return the image and/or metadata if requested.

        Parameters
        ----------
        axes: dict or list of dict
            the axes of the image to wait for. In the case of None, wait for the next image
        return_image: bool
            if True, return the image
        return_metadata: bool
            if True, return the metadata
        """

        if axes is None:
            # wait for the next image to be saved
            with self._condition:
                # wait until something happens
                self._condition.wait()
                while self._last_notification is None or \
                        (not self._last_notification.milestone == AcqNotification.Image.IMAGE_SAVED and \
                        not self._last_notification.milestone == AcqNotification.Image.DATA_SINK_FINISHED):
                    self._condition.wait()
                axes = self._last_notification.payload
        else:
            if isinstance(axes, list):
                keys = [_axes_to_key(ax) for ax in axes]
            else:
                keys = [_axes_to_key(axes)]
            if not self._generator_events and axes is not None:
                # make sure this is a valid axes to wait for associated with this Future
                if any([key not in self._notification_recieved.keys() for key in keys]):
                    raise ValueError("This AcquisitionFuture is not expecting a notification for the given axes")
            # wait until all images are saved
            for key in keys:
                with self._condition:
                    if not self._generator_events:
                        while not self._notification_recieved[key][AcqNotification.Image.IMAGE_SAVED]:
                            self._condition.wait()

        if return_image and return_metadata:
            if isinstance(axes, list):
                return [(self._acq.get_dataset().read_image(**ax), self._acq.get_dataset().read_metadata(**ax)) for ax in axes]
            else:
                return self._acq.get_dataset().read_image(**axes), self._acq.get_dataset().read_metadata(**axes)
        elif return_image:
            if isinstance(axes, list):
                return [self._acq.get_dataset().read_image(**ax) for ax in axes]
            else:
                return self._acq.get_dataset().read_image(**axes)
        elif return_metadata:
            if isinstance(axes, list):
                return [self._acq.get_dataset().read_metadata(**ax) for ax in axes]
            else:
                return self._acq.get_dataset().read_metadata(**axes)


