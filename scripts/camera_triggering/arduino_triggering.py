import threading
import serial
from queue import Queue
import time

def _monitor_port(port, queue):
    serial_port = serial.Serial(port)
    while True:
        if serial_port.inWaiting():
            b = serial_port.read_all()
            trigger_length = int.from_bytes(b, byteorder="big")
            print('Received a {} us trigger'.format(trigger_length))
        elif queue.qsize() > 0:
            try:
                trigger_length = queue.get_nowait()
                serial_port.write(str(trigger_length).encode())
            except:
                pass # threading issue, get it on next pass
        time.sleep(0.001)

class TriggerTester:

    def __init__(self, port):
        self.port = port
        self.output_queue = Queue()
        self.comm_thread = threading.Thread(target=_monitor_port, args=(port, self.output_queue))
        self.comm_thread.start()

    def send_trigger(self, duration_ms):
        self.output_queue.put(duration_ms)


if __name__ == '__main__':
    trigger_arduino = TriggerTester('COM3')
    trigger_arduino.send_trigger(5)