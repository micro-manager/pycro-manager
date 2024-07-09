import os

from pycromanager import start_headless
from pycromanager.execution_engine.devices.implementations.micromanager.mm_device_implementations import (MicroManagerSingleAxisStage,
                                                                                                          MicroManagerCamera)
from pycromanager.execution_engine.kernel.executor import ExecutionEngine

mm_install_dir = '/Users/henrypinkard/Micro-Manager'
config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
start_headless(mm_install_dir, config_file,
               buffer_size_mb=1024, max_memory_mb=1024,  # set these low for github actions
               python_backend=True,
               debug=False)

execution_engine = ExecutionEngine()

z_device = MicroManagerSingleAxisStage('Z')
z_device.UseSequences = 'Yes'

camera_device = MicroManagerCamera('Camera')
camera_device.arm(1)
camera_device.start()


execution_engine.shutdown()
print('done')
pass

