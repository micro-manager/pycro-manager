from typing import List, Union, Tuple
import numpy as np

from pycromanager.execution_engine.kernel.acq_event_base import AcquisitionEvent
from pycromanager.execution_engine.kernel.device_types_base import DoubleAxisPositioner, SingleAxisPositioner

class SetPosition2DEvent(AcquisitionEvent):
    """
    Set the position of a movable device
    """
    device: DoubleAxisPositioner
    position: Tuple[float, float]

    def execute(self):
        self.device.set_position(*self.position)

class SetPositionSequence2DEvent(AcquisitionEvent):
    """
    Set the position of a movable device
    """
    device: DoubleAxisPositioner
    positions: Union[List[Tuple[float, float]], np.ndarray]

    def execute(self):
        self.device.set_position_sequence(self.positions)

class SetPosition1DEvent(AcquisitionEvent):
    """
    Set the position of a movable device
    """
    device: SingleAxisPositioner
    position: float

    def execute(self):
        self.device.set_position(self.position)


class SetPositionSequence1DEvent(AcquisitionEvent):
    """
    Set the position of a movable device
    """
    device: SingleAxisPositioner
    positions: Union[List[float], np.ndarray]

    def execute(self):
        self.device.set_position_sequence(self.positions)