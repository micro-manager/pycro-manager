from pycromanager.execution_engine.events.implementations.positioner_events import SetPosition2DEvent, SetPosition1DEvent
from pycromanager.execution_engine.events.implementations.camera_events import StartCapture, ReadoutImages
from pycromanager.execution_engine.kernel.acq_event_base import AcquisitionEvent
from pycromanager.execution_engine.events.implementations.misc_events import SetTimeEvent, SetChannelEvent
from pycromanager.execution_engine.kernel.device_types_base import SingleAxisPositioner, DoubleAxisPositioner, Camera
from pycromanager.execution_engine.kernel.data_coords import DataCoordinates
from typing import Union, List, Iterable, Optional
import numpy as np
import copy
from itertools import chain

def flatten(lst):
    return list(chain(*[flatten(x) if isinstance(x, list) else [x] for x in lst]))

def multi_d_acquisition_events(
    num_time_points: int = None,
    time_interval_s: Union[float, List[float]] = 0,
    z_start: float = None,
    z_end: float = None,
    z_step: float = None,
    sequence_z=False, # TODO: default this to, "if possible"
    channel_group: str = None,
    channels: list = None,
    channel_exposures_ms: list = None,
    xy_positions: Iterable = None,
    xyz_positions: Iterable = None,
    position_labels: List[str] = None,
    order: str = "tpcz",
    camera: Optional[Union[Camera, str]] = None,
    xy_device: Optional[SingleAxisPositioner] = None,
    z_device: Optional[SingleAxisPositioner] = None,):
    """
    Convenience function for generating the event_implementations of a typical multi-dimensional acquisition (i.e. an
    acquisition with some combination of multiple timepoints, channels, z-slices, or xy positions)

    Parameters
    ----------
    num_time_points : int
        How many time points if it is a timelapse (Default value = None)
    time_interval_s : float or list of floats
        the minimum interval between consecutive time points in seconds. If set to 0, the
        acquisition will go as fast as possible. If a list is provided, its length should
        be equal to 'num_time_points'. Elements in the list are assumed to be the intervals
        between consecutive timepoints in the timelapse. First element in the list indicates
        delay before capturing the first image (Default value = 0)
    z_start : float
        z-stack starting position, in µm. If xyz_positions is given z_start is relative
        to the points' z position. (Default value = None)
    z_end : float
        z-stack ending position, in µm. If xyz_positions is given z_start is
        relative to the points' z position. (Default value = None)
    z_step : float
        step size of z-stack, in µm (Default value = None)
    # TODO: sequence Z
    channel_group : str
        name of the channel group (which should correspond to a config group in micro-manager) (Default value = None)
    channels : list of strings
        list of channel names, which correspond to possible settings of the config group
        (e.g. ['DAPI', 'FITC']) (Default value = None)
    channel_exposures_ms : list of floats or ints
        list of camera exposure times corresponding to each channel. The length of this list
        should be the same as the the length of the list of channels (Default value = None)
    xy_positions : iterable
        An array of shape (N, 2) containing N (X, Y) stage coordinates. (Default value = None)
    xyz_positions : iterable
        An array of shape (N, 3) containing N (X, Y, Z) stage coordinates. (Default value = None).
        If passed then z_start, z_end, and z_step will be relative to the z_position in xyz_positions. (Default value = None)
    position_labels : iterable
        An array of length N containing position labels for each of the XY stage positions. (Default value = None)
    order : str
        string that specifies the order of different dimensions. Must have some ordering of the letters
        c, t, p, and z. For example, 'tcz' would run a timelapse where z stacks would be acquired at each channel in
        series. 'pt' would move to different xy stage positions and run a complete timelapse at each one before moving
        to the next (Default value = 'tpcz')
    camera : Camera
        Camera device object, or string name of the camera device. If None, the camera will be inferred at runtime
    z_device : SingleAxisPositioner
        Z stage device object. If None, the z stage will be inferred at runtime
    xy_device : DoubleAxisPositioner
        XY stage device object. If None, the xy stage will be inferred at runtime

    Returns
    -------
    event_implementations : list[AcquisitionEvent]
        List of AcquisitionEvent objects
    """

    # Input validation
    if xy_positions is not None and xyz_positions is not None:
        raise ValueError("xyz_positions and xy_positions are incompatible arguments that cannot be passed together")

    order = order.lower()
    if "p" in order and "z" in order and order.index("p") > order.index("z"):
        raise ValueError("This function requires that the xy position come earlier in the order than z")

    if isinstance(time_interval_s, list):
        if len(time_interval_s) != num_time_points:
            raise ValueError("Length of time interval list should be equal to num_time_points")

    if position_labels is not None:
        if xy_positions is not None and len(xy_positions) != len(position_labels):
            raise ValueError("xy_positions and position_labels must be of equal length")
        if xyz_positions is not None and len(xyz_positions) != len(position_labels):
            raise ValueError("xyz_positions and position_labels must be of equal length")

    # Z-stack validation
    has_zsteps = False
    if any([z_start, z_step, z_end]):
        if not None in [z_start, z_step, z_end]:
            has_zsteps = True
        else:
            raise ValueError('All of z_start, z_step, and z_end must be provided')

    # Process positions
    z_positions = None
    if xy_positions is not None:
        xy_positions = np.asarray(xy_positions)
        z_positions = None
    elif xyz_positions is not None:
        xyz_positions = np.asarray(xyz_positions)
        xy_positions = xyz_positions[:, :2]
        z_positions = xyz_positions[:, 2][:, None]

    if has_zsteps:
        z_rel = np.arange(z_start, z_end + z_step, z_step)
        if z_positions is None:
            z_positions = z_rel
            if xy_positions is not None:
                z_positions = np.broadcast_to(z_positions, (xy_positions.shape[0], z_positions.shape[0]))
        else:
            pos = []
            for z in z_positions:
                pos.append(z + z_rel)
            z_positions = np.asarray(pos)

    if position_labels is None and xy_positions is not None:
        position_labels = list(range(len(xy_positions)))

    def generate_events(event_list, order, coords=None):
        if coords is None:
            coords = {}
        if len(order) == 0:
            yield event_list, coords
            return
        elif order[0] == "t" and num_time_points is not None and num_time_points > 0:
            time_indices = np.arange(num_time_points)
            if isinstance(time_interval_s, list):
                absolute_start_times = np.cumsum(time_interval_s)
            for time_index in time_indices:
                new_event_list = copy.deepcopy(event_list)
                new_coords = copy.deepcopy(coords)
                if isinstance(time_interval_s, list):
                    min_start_time = absolute_start_times[time_index]
                else:
                    min_start_time = time_index * time_interval_s if time_interval_s != 0 else None
                new_event_list.append(SetTimeEvent(time_index=time_index, min_start_time=min_start_time))
                new_coords['time'] = time_index
                yield from generate_events(new_event_list, order[1:], new_coords)
        elif order[0] == "z" and z_positions is not None:
            for z_index, z in enumerate(z_positions):
                new_event_list = copy.deepcopy(event_list)
                new_coords = copy.deepcopy(coords)
                new_event_list.append(SetPosition1DEvent(device=z_device, position=z))
                new_coords['z'] = z_index
                yield from generate_events(new_event_list, order[1:], new_coords)
        elif order[0] == "p" and xy_positions is not None:
            for p_index, (p_label, xy) in enumerate(zip(position_labels, xy_positions)):
                new_event_list = copy.deepcopy(event_list)
                new_coords = copy.deepcopy(coords)
                new_event_list.append(SetPosition2DEvent(device=xy_device, position=xy))
                new_coords['position'] = p_label
                yield from generate_events(new_event_list, order[1:], new_coords)
        elif order[0] == "c" and channel_group is not None and channels is not None:
            for i, channel in enumerate(channels):
                new_event_list = copy.deepcopy(event_list)
                new_coords = copy.deepcopy(coords)
                exposure = channel_exposures_ms[i] if channel_exposures_ms is not None else None
                new_event_list.append(
                    SetChannelEvent(channel_group=channel_group, channel=channel, exposure_ms=exposure))
                new_coords['channel'] = channel
                yield from generate_events(new_event_list, order[1:], new_coords)
        else:
            # This axis appears to be missing
            yield from generate_events(event_list, order[1:], coords)

        # Generate all event_implementations

    all_events = list(generate_events([], order))

    # Add capture event_implementations to each set of dimension event_implementations
    final_events = []
    for event_set, coords in all_events:
        event_set.append(StartCapture(camera=camera, num_images=1))
        event_set.append(ReadoutImages(camera=camera, num_images=1,
                                       image_coordinate_iterator=[DataCoordinates(**coords)]))
        final_events.append(event_set)

    return flatten(final_events)
