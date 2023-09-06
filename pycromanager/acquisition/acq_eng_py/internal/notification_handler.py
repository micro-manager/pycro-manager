from queue import Queue
import threading

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
        self.notification_queue.put(notification)
        if self.notification_queue.qsize() > 500:
            print(f"Warning: Acquisition notification queue size: {self.notification_queue.qsize()}")

    def add_listener(self, listener):
        self.listeners.append(listener)
