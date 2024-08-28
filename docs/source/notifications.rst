.. _notifications:

==============
Notifications
==============

Acquisitions support a notification system that provides real-time updates on the acquisition process.

To receive notifications, pass a callback function to the ``Acquisition`` constructor. The callback function should accept a single argument, a ``AcqNotification`` object.

   .. code-block:: python

       def notification_callback(notification):
           print(notification.milestone)

       with Acquisition(..., notification_callback_fn=notification_callback) as acq:
           # acquisition code

**Notification Types**: The system provides notifications for various stages of the acquisition process. For example:

   - Acquisition start (``AcqNotification.Acquisition.ACQ_STARTED``)
   - Image saved (``AcqNotification.Image.IMAGE_SAVED``)
   - Acquisition finished (``AcqNotification.Acquisition.ACQ_EVENTS_FINISHED``)
   - Hardware operations (e.g., ``AcqNotification.Hardware.POST_HARDWARE``)

**Notification Content**: Each notification includes a ``milestone`` attribute indicating the specific event that occurred.


