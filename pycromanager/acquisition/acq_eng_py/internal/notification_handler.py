import warnings
from queue import Queue
import queue
import threading
import traceback

class NotificationHandler:
    def __init__(self):
        self.notification_queue = Queue()
        self.listeners = []
        self.run_thread = threading.Thread(target=self.run)
        self.run_thread.start()

    def run(self):
        events_finished = False
        data_sink_finished = False
        while True:
            n = self.notification_queue.get()
            for listener in self.listeners:
                listener.post_notification(n)
            if n.is_acquisition_finished_notification():
                events_finished = True
            if n.is_data_sink_finished_notification():
                data_sink_finished = True
            if events_finished and data_sink_finished:
                break

    def post_notification(self, notification):
            # print(f"NotificationHandler.post_notification: {notification}")
            self.notification_queue.put(notification)
            # print("NotificationHandler.post_notification. size", self.notification_queue.qsize() )
            if self.notification_queue.qsize() > 500:
                warnings.warn(f"Acquisition notification queue size: {self.notification_queue.qsize()}")

    def add_listener(self, listener):
        self.listeners.append(listener)
