from pycromanager import multi_d_acquisition_events
import numpy as np

x = np.arange(0, 5)
y = np.arange(0, -5, -1)
z = np.arange(0, 5)

xy = np.hstack([x[:, None], y[:, None]])
xyz = np.hstack([x[:, None], y[:, None], z[:, None]])


def test_xy_positions():
    expected = [
        {"axes": {"position": 0}, "x": 0, "y": 0},
        {"axes": {"position": 1}, "x": 1, "y": -1},
        {"axes": {"position": 2}, "x": 2, "y": -2},
        {"axes": {"position": 3}, "x": 3, "y": -3},
        {"axes": {"position": 4}, "x": 4, "y": -4},
    ]
    events = multi_d_acquisition_events(xy_positions=xy)
    assert events == expected


def test_xyz_positions():
    expected = [
        {"axes": {"position": 0, "z": 0}, "x": 0, "y": 0, "z": 0},
        {"axes": {"position": 1, "z": 0}, "x": 1, "y": -1, "z": 1},
        {"axes": {"position": 2, "z": 0}, "x": 2, "y": -2, "z": 2},
        {"axes": {"position": 3, "z": 0}, "x": 3, "y": -3, "z": 3},
        {"axes": {"position": 4, "z": 0}, "x": 4, "y": -4, "z": 4},
    ]
    assert expected == multi_d_acquisition_events(xyz_positions=xyz)


def test_xyz_relative_z():
    expected = [
        {"axes": {"position": 0, "z": 0}, "x": 0, "y": 0, "z": -1},
        {"axes": {"position": 0, "z": 1}, "x": 0, "y": 0, "z": 0},
        {"axes": {"position": 0, "z": 2}, "x": 0, "y": 0, "z": 1},
        {"axes": {"position": 1, "z": 0}, "x": 1, "y": -1, "z": 0},
        {"axes": {"position": 1, "z": 1}, "x": 1, "y": -1, "z": 1},
        {"axes": {"position": 1, "z": 2}, "x": 1, "y": -1, "z": 2},
        {"axes": {"position": 2, "z": 0}, "x": 2, "y": -2, "z": 1},
        {"axes": {"position": 2, "z": 1}, "x": 2, "y": -2, "z": 2},
        {"axes": {"position": 2, "z": 2}, "x": 2, "y": -2, "z": 3},
        {"axes": {"position": 3, "z": 0}, "x": 3, "y": -3, "z": 2},
        {"axes": {"position": 3, "z": 1}, "x": 3, "y": -3, "z": 3},
        {"axes": {"position": 3, "z": 2}, "x": 3, "y": -3, "z": 4},
        {"axes": {"position": 4, "z": 0}, "x": 4, "y": -4, "z": 3},
        {"axes": {"position": 4, "z": 1}, "x": 4, "y": -4, "z": 4},
        {"axes": {"position": 4, "z": 2}, "x": 4, "y": -4, "z": 5},
    ]
    assert expected == multi_d_acquisition_events(xyz_positions=xyz, z_start=-1, z_end=1, z_step=1)


def test_xy_absolute_z():
    expected = [
        {"axes": {"position": 0, "z": 0}, "x": 0, "y": 0, "z": -1},
        {"axes": {"position": 0, "z": 1}, "x": 0, "y": 0, "z": 0},
        {"axes": {"position": 0, "z": 2}, "x": 0, "y": 0, "z": 1},
        {"axes": {"position": 1, "z": 0}, "x": 1, "y": -1, "z": -1},
        {"axes": {"position": 1, "z": 1}, "x": 1, "y": -1, "z": 0},
        {"axes": {"position": 1, "z": 2}, "x": 1, "y": -1, "z": 1},
        {"axes": {"position": 2, "z": 0}, "x": 2, "y": -2, "z": -1},
        {"axes": {"position": 2, "z": 1}, "x": 2, "y": -2, "z": 0},
        {"axes": {"position": 2, "z": 2}, "x": 2, "y": -2, "z": 1},
        {"axes": {"position": 3, "z": 0}, "x": 3, "y": -3, "z": -1},
        {"axes": {"position": 3, "z": 1}, "x": 3, "y": -3, "z": 0},
        {"axes": {"position": 3, "z": 2}, "x": 3, "y": -3, "z": 1},
        {"axes": {"position": 4, "z": 0}, "x": 4, "y": -4, "z": -1},
        {"axes": {"position": 4, "z": 1}, "x": 4, "y": -4, "z": 0},
        {"axes": {"position": 4, "z": 2}, "x": 4, "y": -4, "z": 1},
    ]
    assert expected == multi_d_acquisition_events(xy_positions=xy, z_start=-1, z_end=1, z_step=1)


def test_time_points():
    expected = [
        {"axes": {"time": 0}, "min_start_time": 0},
        {"axes": {"time": 1}, "min_start_time": 10},
        {"axes": {"time": 2}, "min_start_time": 20},
        {"axes": {"time": 3}, "min_start_time": 30},
        {"axes": {"time": 4}, "min_start_time": 40},
    ]
    assert expected == multi_d_acquisition_events(num_time_points=5, time_interval_s=10)


def test_order():
    expected = [
        {
            "axes": {"position": 0, "time": 0, "z": 0},
            "x": 0,
            "y": 0,
            "min_start_time": 0,
            "z": -1,
        },
        {
            "axes": {"position": 0, "time": 0, "z": 1},
            "x": 0,
            "y": 0,
            "min_start_time": 0,
            "z": 0,
        },
        {
            "axes": {"position": 0, "time": 1, "z": 0},
            "x": 0,
            "y": 0,
            "min_start_time": 10,
            "z": -1,
        },
        {
            "axes": {"position": 0, "time": 1, "z": 1},
            "x": 0,
            "y": 0,
            "min_start_time": 10,
            "z": 0,
        },
        {
            "axes": {"position": 1, "time": 0, "z": 0},
            "x": 1,
            "y": -1,
            "min_start_time": 0,
            "z": -1,
        },
        {
            "axes": {"position": 1, "time": 0, "z": 1},
            "x": 1,
            "y": -1,
            "min_start_time": 0,
            "z": 0,
        },
        {
            "axes": {"position": 1, "time": 1, "z": 0},
            "x": 1,
            "y": -1,
            "min_start_time": 10,
            "z": -1,
        },
        {
            "axes": {"position": 1, "time": 1, "z": 1},
            "x": 1,
            "y": -1,
            "min_start_time": 10,
            "z": 0,
        },
    ]
    xy_small = xy[:2, :]
    assert expected == multi_d_acquisition_events(
        num_time_points=2,
        time_interval_s=10,
        xy_positions=xy_small,
        order="ptz",
        z_start=-1,
        z_end=0,
        z_step=1,
    )


def test_channels():
    expected = [
        {
            "axes": {"position": 0},
            "x": 0,
            "y": 0,
            "channel": {"group": "your-channel-group", "config": "BF"},
            "exposure": 0,
        },
        {
            "axes": {"position": 0},
            "x": 0,
            "y": 0,
            "channel": {"group": "your-channel-group", "config": "GFP"},
            "exposure": 1,
        },
        {
            "axes": {"position": 1},
            "x": 1,
            "y": -1,
            "channel": {"group": "your-channel-group", "config": "BF"},
            "exposure": 0,
        },
        {
            "axes": {"position": 1},
            "x": 1,
            "y": -1,
            "channel": {"group": "your-channel-group", "config": "GFP"},
            "exposure": 1,
        },
        {
            "axes": {"position": 2},
            "x": 2,
            "y": -2,
            "channel": {"group": "your-channel-group", "config": "BF"},
            "exposure": 0,
        },
        {
            "axes": {"position": 2},
            "x": 2,
            "y": -2,
            "channel": {"group": "your-channel-group", "config": "GFP"},
            "exposure": 1,
        },
        {
            "axes": {"position": 3},
            "x": 3,
            "y": -3,
            "channel": {"group": "your-channel-group", "config": "BF"},
            "exposure": 0,
        },
        {
            "axes": {"position": 3},
            "x": 3,
            "y": -3,
            "channel": {"group": "your-channel-group", "config": "GFP"},
            "exposure": 1,
        },
        {
            "axes": {"position": 4},
            "x": 4,
            "y": -4,
            "channel": {"group": "your-channel-group", "config": "BF"},
            "exposure": 0,
        },
        {
            "axes": {"position": 4},
            "x": 4,
            "y": -4,
            "channel": {"group": "your-channel-group", "config": "GFP"},
            "exposure": 1,
        },
    ]
    channel_group = "your-channel-group"
    channels = ["BF", "GFP"]
    channel_exposures_ms = [15.5, 200]
    assert expected == multi_d_acquisition_events(
        xy_positions=xy,
        channels=channels,
        channel_group=channel_group,
        channel_exposures_ms=channel_exposures_ms,
    )
