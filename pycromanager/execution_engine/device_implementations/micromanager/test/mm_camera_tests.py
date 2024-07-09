import pytest
import time
import os
import itertools
from pycromanager import start_headless
from pycromanager.execution_engine.kernel.executor import ExecutionEngine
from pycromanager.execution_engine.kernel.data_handler import DataHandler
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from pycromanager.execution_engine.device_implementations.micromanager.mm_device_implementations import MicroManagerCamera
from pycromanager.execution_engine.storage_implementations.NDTiffandRAM import NDRAMStorage
from pycromanager.execution_engine.kernel.

@pytest.fixture(scope="module")
def setup_micromanager():
    mm_install_dir = '/Users/henrypinkard/Micro-Manager'
    config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
    start_headless(mm_install_dir, config_file,
                   buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
                   python_backend=True,
                   debug=False)
    yield
    # No specific teardown needed for start_headless

@pytest.fixture(scope="module")
def executor():
    executor = ExecutionEngine()
    yield executor
    executor.shutdown()

@pytest.fixture
def camera():
    return MicroManagerCamera()

def capture_images(num_images, executor, camera):
    storage = NDRAMStorage()
    data_handler = DataHandler(storage=storage)

    start_capture_event = StartCapture(num_images=num_images, camera=camera)
    readout_images_event = ReadoutImages(num_images=num_images, camera=camera,
                                         image_coordinate_iterator=[DataCoordinates(time=t) for t in range(num_images)],
                                         data_handler=data_handler)

    executor.submit([start_capture_event, readout_images_event])

    while not {'time': num_images - 1} in storage:
        time.sleep(1)

    data_handler.finish()

@pytest.mark.usefixtures("setup_micromanager")
def test_finite_sequence(executor, camera):
    capture_images(100, executor, camera)
    print('Finished first one')

@pytest.mark.usefixtures("setup_micromanager")
def test_single_image(executor, camera):
    capture_images(1, executor, camera)
    print('Finished single image')

@pytest.mark.usefixtures("setup_micromanager")
def test_multiple_single_image_captures(executor, camera):
    for _ in range(5):
        capture_images(1, executor, camera)
    print('Finished multiple single image captures')


@pytest.mark.usefixtures("setup_micromanager")
def test_continuous_capture(executor, camera):
    storage = NDRAMStorage()
    data_handler = DataHandler(storage=storage)

    start_capture_event = StartContinuousCapture(camera=camera)
    readout_images_event = ReadoutImages(camera=camera,
                                         image_coordinate_iterator=(DataCoordinates(time=t) for t in itertools.count()),
                                         data_handler=data_handler)
    stop_capture_event = StopCapture(camera=camera)

    _, readout_future, _ = executor.submit([start_capture_event, readout_images_event, stop_capture_event])
    time.sleep(2)
    readout_future.stop(await_completion=True)

    data_handler.finish()
    print('Finished continuous capture')