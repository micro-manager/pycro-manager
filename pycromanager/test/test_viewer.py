import os
import pytest
from pycromanager import Acquisition, Core, multi_d_acquisition_events

# Skip tests in this module if it is running in GitHub Actions, which does not support NDViewer
# https://docs.pytest.org/en/7.1.x/how-to/skipping.html
# https://docs.github.com/ko/actions/learn-github-actions/variables
pytestmark = pytest.mark.skipif(os.getenv('GITHUB_ACTIONS') is True)

def test_multi_d_acq_viewer(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
        channel_group="Channel",
        channels=["DAPI", "FITC"],
        z_start=0,
        z_end=5,
        z_step=1,
        order="tcz",
    )

    with Acquisition(setup_data_folder, 'acq', show_display=True) as acq:
        acq.acquire(events)

    dataset = acq.get_dataset()

    for t in range(10):
        for z in range(6):
            for ch in ["DAPI", "FITC"]:
                assert dataset.has_image(time=t, channel=ch, z=z)

    data = dataset.as_array(axes=['time', 'channel', 'z'])
    assert data.shape[:-2] == (10, 2, 6)
    dataset.close()
