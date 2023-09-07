import os
import pytest
from pycromanager import Acquisition, Core, multi_d_acquisition_events
import napari

# Skip tests in this module if it is running in GitHub Actions, which does not support NDViewer
# https://docs.pytest.org/en/7.1.x/how-to/skipping.html
# https://docs.github.com/ko/actions/learn-github-actions/variables
pytestmark = pytest.mark.skipif(os.getenv('GITHUB_ACTIONS') == 'true', reason="NDViewer does not work in GitHub Actions")

def test_timelapse_NDViewer(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
    )

    with Acquisition(setup_data_folder, 'acq', show_display=True) as acq:
        acq.acquire(events)

    # close viewer
    acq.get_viewer().close()


def test_multi_d_acq_NDViewer(launch_mm_headless, setup_data_folder):
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

    # close viewer
    acq.get_viewer().close()


def test_timelapse_napari_viewer(launch_mm_headless, setup_data_folder):
    events = multi_d_acquisition_events(
        num_time_points=10,
        time_interval_s=0,
    )

    viewer = napari.Viewer()

    acq = Acquisition(setup_data_folder, 'acq', napari_viewer=viewer)
    acq.acquire(events)
    acq.mark_finished()

    napari.run()
    acq.get_dataset().close()
    acq.await_completion()


def test_multi_d_acq_napari_viewer(launch_mm_headless, setup_data_folder):
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

    viewer = napari.Viewer()

    acq = Acquisition(setup_data_folder, 'acq', napari_viewer=viewer)
    acq.acquire(events)
    acq.mark_finished()

    napari.run()
    acq.get_dataset().close()
    acq.await_completion()

