import os
import numpy as np

from pycromanager import start_headless
from pycromanager.execution_engine.devices.implementations.micromanager.mm_device_implementations import (MicroManagerSingleAxisStage,
                                                                                                          MicroManagerXYStage, MicroManagerCamera)
from pycromanager.execution_engine.kernel.executor import ExecutionEngine
from pycromanager.execution_engine.kernel.data_handler import DataHandler
from pycromanager.execution_engine.kernel.acq_event_base import DataProducing
from pycromanager.execution_engine.storage.NDTiffandRAM import NDRAMStorage
from pycromanager.execution_engine.events.implementations.positioner_events import (SetPosition1DEvent,
                                                                                    SetPosition2DEvent,
                                                                                    SetPositionSequence1DEvent)
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from pycromanager.execution_engine.events.implementations.camera_events import StartCapture, ReadoutImages
from pycromanager.execution_engine.events.multi_d_events import multi_d_acquisition_events

mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)

execution_engine = ExecutionEngine()

z_device = MicroManagerSingleAxisStage('Z')
camera_device = MicroManagerCamera()
xy_device = MicroManagerXYStage()


# Example usage
events = multi_d_acquisition_events(
    camera=camera_device,
    # num_time_points=10,
    # time_interval_s=0,
    # channel_group="Channel",
    # channels=["DAPI", "FITC"],
    z_device=z_device,
    z_start=0,
    z_end=20,
    z_step=4,
    order="tcz",
)

# Run an acquisition
storage = NDRAMStorage()
data_handler = DataHandler(storage)
for e in events:

    # TODO: Acquisition should do this automatically
    if isinstance(e, DataProducing):
        e.data_handler = data_handler
    elif isinstance(e, SetPosition1DEvent):
        e.device = z_device
    elif isinstance(e, SetPosition2DEvent):
        e.device = xy_device

    print(e)
    future = execution_engine.submit(e)

future.await_execution()
means = [storage[{'z': i}].mean() for i in range(5)]
# verify that the mean decreases with z
assert all(means[i] > means[i + 1] for i in range(4))



#######
# Sequenced Z stack

storage = NDRAMStorage()
data_handler = DataHandler(storage)

z_device.UseSequences = 'Yes'

z_positions = np.arange(0, 20, 4)
z_sequence = SetPositionSequence1DEvent(device=z_device, positions=z_positions)
start_capture_event = StartCapture(camera=camera_device, num_images=len(z_positions))
readout_event = ReadoutImages(camera=camera_device,
                              image_coordinate_iterator=(DataCoordinates(z=z) for z in range(len(z_positions))),
                              data_handler=data_handler)


# TODO: StopSequenceEvent
_, _, future = execution_engine.submit([z_sequence, start_capture_event, readout_event])

future.await_execution()

means = [storage[{'z': i}].mean() for i in range(len(z_positions))]

