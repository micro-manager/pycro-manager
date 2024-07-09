import time
import warnings

from pycromanager.execution_engine.kernel.acq_event_base import AcquisitionEvent
from typing import Optional


class Sleep(AcquisitionEvent):
    """
    Sleep for a specified amount of time
    """
    time_s: int

    def execute(self):
        time.sleep(self.time_s)

# TODO: should this be set start time event?
class SetTimeEvent(AcquisitionEvent):
    """Set the time point"""
    # TODO: why is time index needed??
    time_index: int
    min_start_time: Optional[float] = None

    def execute(self):
        # TODO: delay until ready??
        warnings.warn("SetTimeEvent not implemented")


# TODO:
class SetChannelEvent(AcquisitionEvent):
    """Set the channel configuration"""
    channel_group: str
    channel: str
    exposure_ms: Optional[float] = None

    def execute(self):
        # TODO
        warnings.warn("SetChannelEvent not implemented")