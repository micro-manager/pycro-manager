from pycromanager import Core
from pycromanager.acq_eng_py.internal.engine import Engine
from pycromanager.acq_eng_py.main.acquisition_py import Acquisition
from pycromanager import multi_d_acquisition_events
from pycromanager.acq_eng_py.main.acquisition_event import AcquisitionEvent
import time

core = Core()
engine = Engine(core)

class DataSink:
    def initialize(self, acq, summary_metadata: dict):
        pass

    def finish(self):
        pass

    def is_finished(self) -> bool:
        return True

    def put_image(self, image: dict):
        print('image')

    def anything_acquired(self) -> bool:
        return False


sink = DataSink()
acq = Acquisition(sink)

events = multi_d_acquisition_events(num_time_points=6)
events = [AcquisitionEvent.from_json(e, acq) for e in events]
acq.submit_event_iterator(events)

while not acq.are_events_finished():
    time.sleep(0.1)
print('completed')
