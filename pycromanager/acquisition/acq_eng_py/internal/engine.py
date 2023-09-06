import traceback
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
import time
import datetime

from pycromanager.acquisition.acq_eng_py.main.acquisition_event import AcquisitionEvent
from pycromanager.acquisition.acq_eng_py.main.acq_eng_metadata import AcqEngMetadata
from pycromanager.acquisition.acq_eng_py.internal.hardware_sequences import HardwareSequences
import pymmcore
from pycromanager.acquisition.acq_eng_py.main.acq_notification import AcqNotification

HARDWARE_ERROR_RETRIES = 6
DELAY_BETWEEN_RETRIES_MS = 5

class HardwareControlException(Exception):
    def __init__(self, message=""):
        super().__init__(message)

class Engine:
    def __init__(self, core):
        if not hasattr(Engine, 'singleton'):
            Engine.singleton = self
            self.last_event = None
            self.core = core
            self.acq_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Acquisition Engine Thread')
            self.event_generator_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Acq Eng event generator')
            self.sequenced_events = []

    def shutdown(self):
        self.acq_executor.shutdown()
        self.event_generator_executor.shutdown()

    @staticmethod
    def get_core():
        return Engine.singleton.core

    @staticmethod
    def get_instance():
        return Engine.singleton

    def finish_acquisition(self, acq):
        def finish_acquisition_inner():
            if acq.is_debug_mode():
                Engine.get_core().logMessage("recieved acquisition finished signal")
            self.sequenced_events.clear()
            if acq.is_debug_mode():
                Engine.get_core().logMessage("creating acquisition finished event")
            self.execute_acquisition_event(AcquisitionEvent.create_acquisition_finished_event(acq))
            acq.block_until_events_finished()

        return self.event_generator_executor.submit(finish_acquisition_inner)

    def submit_event_iterator(self, event_iterator):
        def submit_event_iterator_inner():
            acq = None
            while True:
                try:
                    event = next(event_iterator, None)
                except StopIteration:
                    traceback.print_exc()
                    break
                if event is None:
                    break # iterator exhausted
                acq = event.acquisition_
                if acq.is_debug_mode():
                    Engine.get_core().logMessage("got event: " + event.to_string())
                for h in event.acquisition_.get_event_generation_hooks():
                    event = h.run(event)
                    if event is None:
                        return
                while event.acquisition_.is_paused():
                    time.sleep(0.005)
                try:
                    if acq.is_abort_requested():
                        if acq.is_debug_mode():
                            Engine.get_core().logMessage("acquisition aborted")
                        return
                    image_acquired_future = self.process_acquisition_event(event)
                    image_acquired_future.result()

                except Exception as ex:
                    traceback.print_exc()
                    acq.abort(ex)
                    raise ex

            last_image_future = self.process_acquisition_event(AcquisitionEvent.create_acquisition_sequence_end_event(acq))
            last_image_future.result()


        return self.event_generator_executor.submit(submit_event_iterator_inner)
    

    def process_acquisition_event(self, event: AcquisitionEvent) -> Future:
        def process_acquisition_event_inner():
            try:
                if event.acquisition_.is_debug_mode():
                    self.core.logMessage("Processing event: " + event.to_string())
                if event.acquisition_.is_debug_mode():
                    self.core.logMessage("checking for sequencing")
                if not self.sequenced_events and not event.is_acquisition_sequence_end_event():
                    self.sequenced_events.append(event)
                elif self.is_sequencable(self.sequenced_events, event, len(self.sequenced_events) + 1):
                    # merge event into the sequence
                    self.sequenced_events.append(event)
                else:
                    # all events
                    sequence_event = self.merge_sequence_event(self.sequenced_events)
                    self.sequenced_events.clear()
                    # Add in the start of the new sequence
                    if not event.is_acquisition_sequence_end_event():
                        self.sequenced_events.append(event)
                    if event.acquisition_.is_debug_mode():
                        self.core.logMessage("executing acquisition event")
                    try:
                        self.execute_acquisition_event(sequence_event)
                    except HardwareControlException as e:
                        raise e
            except Exception as e:
                traceback.print_exc()
                if self.core.is_sequence_running():
                    self.core.stop_sequence_acquisition()
                raise e


        return self.acq_executor.submit(process_acquisition_event_inner)

    def execute_acquisition_event(self, event: AcquisitionEvent):
        # check if we should pause until the minimum start time of the event has occured
        while event.get_minimum_start_time_absolute() is not None and \
                time.time() * 1000 < event.get_minimum_start_time_absolute():
            wait_time = event.get_minimum_start_time_absolute() - time.time() * 1000
            event.acquisition_.block_unless_aborted(wait_time)

        if event.is_acquisition_finished_event():
            # signal to finish saving thread and mark acquisition as finished
            if event.acquisition_.are_events_finished():
                return  # Duplicate finishing event, possibly from x-ing out viewer

            # send message acquisition finished message so things shut down properly
            for h in event.acquisition_.get_event_generation_hooks():
                h.run(event)
                h.close()
            for h in event.acquisition_.get_before_hardware_hooks():
                h.run(event)
                h.close()
            for h in event.acquisition_.get_after_hardware_hooks():
                h.run(event)
                h.close()
            for h in event.acquisition_.get_after_camera_hooks():
                h.run(event)
                h.close()
            for h in event.acquisition_.get_after_exposure_hooks():
                h.run(event)
                h.close()
            event.acquisition_.add_to_output(self.core.TaggedImage(None, None))
            event.acquisition_.post_notification(AcqNotification.create_acq_events_finished_notification())

        else:
            event.acquisition_.post_notification(AcqNotification(
                AcqNotification.Hardware, event.axisPositions_, AcqNotification.Hardware.PRE_HARDWARE))
            for h in event.acquisition_.get_before_hardware_hooks():
                event = h.run(event)
                if event is None:
                    return  # The hook cancelled this event
                self.abort_if_requested(event, None)
            hardware_sequences_in_progress = HardwareSequences()
            try:
                self.prepare_hardware(event, hardware_sequences_in_progress)
            except HardwareControlException as e:
                self.stop_hardware_sequences(hardware_sequences_in_progress)
                raise e
            # TODO restore this
            event.acquisition_.post_notification(AcqNotification(
                AcqNotification.Hardware, event.axisPositions_, AcqNotification.Hardware.POST_HARDWARE))
            for h in event.acquisition_.get_after_hardware_hooks():
                event = h.run(event)
                if event is None:
                    return  # The hook cancelled this event
                self.abort_if_requested(event, hardware_sequences_in_progress)
            # Hardware hook may have modified wait time, so check again if we should
            # pause until the minimum start time of the event has occurred.
            while event.get_minimum_start_time_absolute() is not None and \
                    time.time() * 1000 < event.get_minimum_start_time_absolute():
                try:
                    self.abort_if_requested(event, hardware_sequences_in_progress)
                    wait_time = event.get_minimum_start_time_absolute() - time.time() * 1000
                    event.acquisition_.block_unless_aborted(wait_time)
                except Exception:
                    # Abort while waiting for next time point
                    return

            if event.should_acquire_image():
                if event.acquisition_.is_debug_mode():
                    self.core.logMessage("acquiring image(s)")
                try:
                    self.acquire_images(event, hardware_sequences_in_progress)
                except TimeoutError:
                    # Don't abort on a timeout
                    # TODO: this could probably be an option added to the acquisition in the future
                    print("Timeout while acquiring images")

                # if the acquisition was aborted, make sure everything shuts down properly
                self.abort_if_requested(event, hardware_sequences_in_progress)

        
    def acquire_images(self, event: AcquisitionEvent, hardware_sequences_in_progress: HardwareSequences) -> None:
        """
        Acquire 1 or more images in a sequence, add some metadata, then
        put them into an output queue.

        If the event is a sequence and a sequence acquisition is started in the core,
        It should be completed by the time this method returns.
        """
        camera_image_counts = event.get_camera_image_counts(self.core.get_camera_device())
        if event.get_sequence() is not None and len(event.get_sequence()) > 1:
            # start sequences on one or more cameras
            for camera_device_name, image_count in camera_image_counts.items():
                event.acquisition_.post_notification(AcqNotification(
                    AcqNotification.Camera, event.axisPositions_, AcqNotification.Camera.PRE_SEQUENCE_STARTED))
                self.core.start_sequence_acquisition(
                    camera_device_name, camera_image_counts[camera_device_name], 0, True)
        else:
            # snap one image with no sequencing
            event.acquisition_.post_notification(AcqNotification(
                AcqNotification.Camera, event.axisPositions_, AcqNotification.Camera.PRE_SNAP))
            if event.get_camera_device_name() is not None:
                current_camera = self.core.get_camera_device()
                width = self.core.get_image_width()
                height = self.core.get_image_height()
                self.core.set_camera_device(event.get_camera_device_name())
                self.core.snap_image()
                self.core.set_camera_device(current_camera)
            else:
                # Unlike MMCoreJ, pymmcore does not automatically add this metadata when snapping, so need to do it manually
                width = self.core.get_image_width()
                height = self.core.get_image_height()
                self.core.snap_image()
            event.acquisition_.post_notification(AcqNotification(
                AcqNotification.Camera, event.axisPositions_, AcqNotification.Camera.POST_EXPOSURE))
            for h in event.acquisition_.get_after_exposure_hooks():
                h.run(event)
        
        # get elapsed time
        current_time_ms = time.time() * 1000
        if event.acquisition_.get_start_time_ms() == -1:
            # first image, initialize
            event.acquisition_.set_start_time_ms(current_time_ms)

        # need to assign events to images as they come out, assuming they might be in arbitrary order,
        # but that each camera itself is ordered
        multi_cam_adapter_camera_event_lists = None
        if event.get_sequence() is not None:
            multi_cam_adapter_camera_event_lists = {}
            for cam_index in range(self.core.get_number_of_camera_channels()):
                multi_cam_adapter_camera_event_lists[cam_index] = []
                for e in event.get_sequence():
                    multi_cam_adapter_camera_event_lists[cam_index].append(e)

        # Run a hook after the camera sequence acquisition has started. This can be used for
        # external triggering of the camera (when it is in sequence mode).
        # note: SnapImage will block until exposure finishes.
        # If it is desired that AfterCameraHooks trigger cameras
        # in Snap mode, one possibility is that those hooks (or SnapImage) should run
        # in a separate thread, started after snapImage is started. But there is no
        # guarantee that the camera will be ready to accept a trigger at that point.
        for h in event.acquisition_.get_after_camera_hooks():
            h.run(event)

        if event.acquisition_.is_debug_mode():
            self.core.log_message("images acquired, copying from core")
        start_copy_time = time.time()
        # Loop through and collect all acquired images. There will be
        # (# of images in sequence) x (# of camera channels) of them
        timeout = False
        for i in range(0, 1 if event.get_sequence() is None else len(event.get_sequence())):
            if timeout:
                # Cancel the rest of the sequence
                self.stop_hardware_sequences(hardware_sequences_in_progress)
                break
            try:
                exposure = self.core.get_exposure() if event.get_exposure() is None else event.get_exposure()
            except Exception as ex:
                raise Exception("Couldnt get exposure form core")
            num_cam_channels = self.core.get_number_of_camera_channels()

            need_to_run_after_exposure_hooks = len(event.acquisition_.get_after_exposure_hooks()) > 0
            for cam_index in range(num_cam_channels):
                ti = None
                camera_name = None
                while ti is None:
                    if event.acquisition_.is_abort_requested():
                        return
                    try:
                        if event.get_sequence() is not None and len(event.get_sequence()) > 1:
                            if self.core.is_buffer_overflowed():
                                raise Exception("Sequence buffer overflow")
                            try:
                                ti = self.core.pop_next_tagged_image()
                                camera_name = ti.tags["Camera"]
                            except Exception as e:
                                # continue waiting
                                if not self.core.is_sequence_running() and self.core.get_remaining_image_count() == 0:
                                    raise Exception("Expected images did not arrive in circular buffer")
                                # check if timeout has been exceeded. This is used in the case of a
                                # camera waiting for a trigger that never comes.
                                if event.get_sequence()[i].get_timeout_ms() is not None:
                                    if time.time() - start_copy_time > event.get_sequence()[i].get_timeout_ms():
                                        timeout = True
                                        self.core.stop_sequence_acquisition()
                                        while self.core.is_sequence_running():
                                            time.sleep(0.001)
                                        break
                        else:
                            try:
                                # TODO: probably there should be a timeout here too, but I'm
                                #  not sure the snap_image system supports it (as opposed to sequences)
                                # This is a little different from the java version due to differences in metadata
                                # handling in the SWIG wrapper
                                camera_name = self.core.get_camera_device()
                                ti = self.core.get_tagged_image(self, cam_index, camera_name, height, width)
                            except Exception as e:
                                # continue waiting
                                pass
                    except Exception as ex:
                        # Sequence buffer overflow
                        e = HardwareControlException(str(ex))
                        event.acquisition_.abort(e)
                        raise e
                if need_to_run_after_exposure_hooks:
                    for camera_device_name in camera_image_counts.keys():
                        if self.core.is_sequence_running(camera_device_name):
                            # all of the sequences are not yet done, so this will need to be handled
                            # on another iteration of the loop
                            break
                    event.acquisition_.post_notification(AcqNotification(
                        AcqNotification.Camera, event.axisPositions_, AcqNotification.Camera.POST_EXPOSURE))
                    for h in event.acquisition_.get_after_exposure_hooks():
                        h.run(event)
                    need_to_run_after_exposure_hooks = False

                if timeout:
                    break
                # Doesn't seem to be a version in the API in which you don't have to do this
                actual_cam_index = cam_index
                if "Multi Camera-CameraChannelIndex" in ti.tags.keys() :
                    actual_cam_index = ti.tags["Multi Camera-CameraChannelIndex"]
                    if num_cam_channels == 1:
                        # probably a mistake in the core....
                        actual_cam_index = 0  # Override index because not using multi cam mode right now

                corresponding_event = event
                if event.get_sequence() is not None:
                    # Find the event that corresponds to the camera that captured this image.
                    # This assumes that the images from a single camera are in order
                    # in the sequence, though different camera images may be interleaved
                    if event.get_sequence()[0].get_camera_device_name() is not None:
                        # camera is specified in the acquisition event. Find the first event that matches
                        # this camera name.
                        the_camera_name = camera_name
                        corresponding_event = next(filter(lambda
                                                              e: e.get_camera_device_name() is not None and e.get_camera_device_name() == the_camera_name,
                                                          multi_cam_adapter_camera_event_lists.get(actual_cam_index)))
                        multi_cam_adapter_camera_event_lists.get(actual_cam_index).remove(corresponding_event)
                    else:
                        # multi camera adapter or just using the default camera
                        corresponding_event = multi_cam_adapter_camera_event_lists.get(actual_cam_index).pop(0)
                # add standard metadata
                AcqEngMetadata.add_image_metadata(self.core, ti.tags, corresponding_event,
                                                  current_time_ms - corresponding_event.acquisition_.get_start_time_ms(),
                                                  exposure)
                # add user metadata specified in the event
                corresponding_event.acquisition_.add_tags_to_tagged_image(ti.tags, corresponding_event.get_tags())
                corresponding_event.acquisition_.add_to_image_metadata(ti.tags)
                corresponding_event.acquisition_.add_to_output(ti)

        if timeout:
            raise TimeoutError("Timeout waiting for images to arrive in circular buffer")

    def abort_if_requested(self, event: AcquisitionEvent, hardware_sequences_in_progress: HardwareSequences) -> None:
        if event.acquisition_.is_abort_requested():
            if hardware_sequences_in_progress is not None:
                self.stop_hardware_sequences(hardware_sequences_in_progress)

    def stop_hardware_sequences(self, hardware_sequences_in_progress: HardwareSequences) -> None:
        # Stop any hardware sequences
        for device_name in hardware_sequences_in_progress.device_names:
            try:
                if str(self.core.getDeviceType(device_name)) == "StageDevice":
                    str(self.core.stopStageSequence(device_name))
                elif str(self.core.getDeviceType(device_name)) == "XYStageDevice":
                    self.core.stopXYStageSequence(device_name)
                elif (self.core.getDeviceType(device_name)) == "CameraDevice":
                    self.core.stopSequenceAcquisition(self.core.getCameraDevice())
            except Exception as ee:
                traceback.print_exc()
                self.core.logMessage("Error stopping hardware sequence: ")
        # Stop any property sequences
        for i in range(len(hardware_sequences_in_progress.property_names)):
            try:
                self.core.stopPropertySequence(hardware_sequences_in_progress.property_device_names[i],
                                            hardware_sequences_in_progress.property_names[i])
            except Exception as ee:
                traceback.print_exc()
                self.core.logMessage("Error stopping property sequence: " + ee)
        self.core.clear_circular_buffer()


    def prepare_hardware(self, event: AcquisitionEvent, hardware_sequences_in_progress: HardwareSequences) -> None:
        def move_xy_stage(event):
            try:
                if event.is_xy_sequenced():
                    self.core.start_xy_stage_sequence(xy_stage)
                else:
                    # Could be sequenced over other devices, in that case get xy position from first in sequence
                    prev_x_position = None if self.last_event is None else None if self.last_event.get_sequence() is None else \
                        self.last_event.get_sequence()[0].get_x_position()
                    x_position = event.get_sequence()[
                        0].get_x_position() if event.get_sequence() is not None else event.get_x_position()
                    prev_y_position = None if self.last_event is None else None if self.last_event.get_sequence() is None else \
                        self.last_event.get_sequence()[0].get_y_position()
                    y_position = event.get_sequence()[
                        0].get_y_position() if event.get_sequence() is not None else event.get_y_position()
                    previous_xy_defined = event is not None and prev_x_position is not None and prev_y_position is not None
                    current_xy_defined = event is not None and x_position is not None and y_position is not None
                    if not current_xy_defined:
                        return
                    xy_changed = not previous_xy_defined or not prev_x_position == x_position or not prev_y_position == y_position
                    if not xy_changed:
                        return
                    # Wait for it to not be busy (is this even needed?)
                    self.core.wait_for_device(xy_stage)
                    # Move XY
                    self.core.set_xy_position(xy_stage, x_position, y_position)
                    # Wait for move to finish
                    self.core.wait_for_device(xy_stage)
            except Exception as ex:
                self.core.log_message(traceback.format_exc())
                raise HardwareControlException()

        def change_channels(event):
            try:
                # Get the values of current channel, pulling from the first event in a sequence if one is present
                current_config = event.get_sequence()[
                    0].get_config_preset() if event.get_sequence() is not None else event.get_config_preset()
                current_group = event.get_sequence()[
                    0].get_config_group() if event.get_sequence() is not None else event.get_config_group()
                previous_config = None if self.last_event is None else None if self.last_event.get_sequence() is None else \
                    self.last_event.get_sequence()[0].get_config_preset()
                new_channel = current_config is not None and (
                        previous_config is None or not previous_config == current_config)
                if new_channel:
                    # Set exposure
                    if event.get_exposure() is not None:
                        self.core.set_exposure(event.get_exposure())
                    # Set other channel props
                    self.core.set_config(current_group, current_config)
                    # TODO: haven't tested if this is actually needed
                    self.core.wait_for_config(current_group, current_config)
                if event.is_config_group_sequenced():
                    # Channels
                    group = event.get_sequence()[0].get_config_group()
                    config = self.core.get_config_data(group, event.get_sequence()[0].get_config_preset())
                    for i in range(config.size()):
                        ps = config.get_setting(i)
                        device_name = ps.get_device_label()
                        prop_name = ps.get_property_name()
                        if self.core.is_property_sequenceable(device_name, prop_name):
                            self.core.start_property_sequence(device_name, prop_name)
            except Exception as ex:
                ex.print_stack_trace()
                raise HardwareControlException(ex.get_message())

        def move_z_device(event):
            try:
                if event.is_z_sequenced():
                    self.core.start_stage_sequence(z_stage)
                else:
                    previous_z = None if self.last_event is None else None if self.last_event.get_sequence() is None else \
                        self.last_event.get_sequence()[0].get_z_position()
                    current_z = event.get_z_position() if event.get_sequence() is None else \
                        event.get_sequence()[0].get_z_position()
                    if current_z is None:
                        return
                    change = previous_z is None or previous_z != current_z
                    if not change:
                        return

                    # Wait for it to not be busy
                    self.core.wait_for_device(z_stage)
                    # Move Z
                    self.core.set_position(z_stage, float(current_z))
                    # Wait for move to finish
                    self.core.wait_for_device(z_stage)
            except Exception as ex:
                raise HardwareControlException(ex)

        def move_other_stage_devices(event):
            try:
                for stage_device_name in event.get_stage_device_names():
                    # Wait for it to not be busy
                    self.core.wait_for_device(stage_device_name)
                    # Move stage device
                    self.core.set_position(stage_device_name,
                                           event.get_stage_single_axis_stage_position(stage_device_name))
                    # Wait for move to finish
                    self.core.wait_for_device(stage_device_name)
            except Exception as ex:
                raise HardwareControlException(ex)

        def change_exposure(event):
            try:
                if event.is_exposure_sequenced():
                    self.core.start_exposure_sequence(self.core.get_camera_device())
                else:
                    current_exposure = event.get_exposure()
                    prev_exposure = None if self.last_event is None else self.last_event.get_exposure()
                    change_exposure = current_exposure is not None and (prev_exposure is None or
                                                                        not prev_exposure == current_exposure)
                    if change_exposure:
                        self.core.setExposure(current_exposure)
            except Exception as ex:
                raise HardwareControlException(ex)

        def set_slm_pattern(event):
            try:
                slm_image = event.get_slm_image()
                if slm_image is not None:
                    if isinstance(slm_image, bytes):
                        self.core.get_slm_image(slm, slm_image)
                    elif isinstance(slm_image, list) and all(isinstance(i, int) for i in slm_image):
                        self.core.get_slm_image(slm, slm_image)
                    else:
                        raise ValueError("SLM api only supports 8 bit and 32 bit patterns")
            except Exception as ex:
                raise HardwareControlException(ex)

        def loop_hardware_command_retries(r, command_name):
            for i in range(HARDWARE_ERROR_RETRIES):
                try:
                    r()
                    return
                except Exception as e:
                    self.core.log_message(traceback.format_exc())
                    print(self.get_current_date_and_time() + ": Problem " + command_name + "\n Retry #" + str(
                        i) + " in " + str(DELAY_BETWEEN_RETRIES_MS) + " ms")
                    time.sleep(DELAY_BETWEEN_RETRIES_MS / 1000)
            raise HardwareControlException(command_name + " unsuccessful")

        def change_additional_properties(event):
            try:
                for s in event.get_additional_properties():
                    self.core.setProperty(s[0], s[1], s[2])
            except Exception as ex:
                raise HardwareControlException(ex.getMessage())

        try:
            # Get the hardware specific to this acquisition
            xy_stage = self.core.get_xy_stage_device()
            z_stage = self.core.get_focus_device()
            slm = self.core.get_slm_device()

            # Prepare sequences if applicable
            if event.get_sequence() is not None:
                z_sequence = pymmcore.DoubleVector() if event.is_z_sequenced() else None
                x_sequence = pymmcore.DoubleVector() if event.is_xy_sequenced() else None
                y_sequence = pymmcore.DoubleVector() if event.is_xy_sequenced() else None
                exposure_sequence_ms = pymmcore.DoubleVector() if event.is_exposure_sequenced() else None
                group = event.get_sequence()[0].get_config_group()
                config = self.core.get_config_data(group, event.get_sequence()[0].get_config_preset()) if event.get_sequence()[0].get_config_preset() is not None else None
                prop_sequences = [] if event.is_config_group_sequenced() else None

                for e in event.get_sequence():
                    if z_sequence is not None:
                        z_sequence.add(e.get_z_position())
                    if x_sequence is not None:
                        x_sequence.add(e.get_x_position())
                    if y_sequence is not None:
                        y_sequence.add(e.get_y_position())
                    if exposure_sequence_ms is not None:
                        exposure_sequence_ms.add(e.get_exposure())

                    # Set sequences for all channel properties
                    if prop_sequences is not None:
                        for i in range(config.size()):
                            ps = config.get_setting(i)
                            device_name = ps.get_device_label()
                            prop_name = ps.get_property_name()

                            if e == event.get_sequence()[0]:  # First property
                                # TODO: what is this in pymmcore
                                prop_sequences.add(StrVector())

                            channel_preset_config = self.core.get_config_data(group, e.get_config_preset())
                            prop_value = channel_preset_config.get_setting(device_name, prop_name).get_property_value()

                            if self.core.is_property_sequenceable(device_name, prop_name):
                                prop_sequences.get(i).add(prop_value)

                    hardware_sequences_in_progress.device_names.append(self.core.get_camera_device())

                    # Now have built up all the sequences, apply them
                    if event.is_exposure_sequenced():
                        self.core.load_exposure_sequence(self.core.get_camera_device(), exposure_sequence_ms)
                        # Already added camera

                    if event.is_xy_sequenced():
                        self.core.load_xy_stage_sequence(xy_stage, x_sequence, y_sequence)
                        hardware_sequences_in_progress.device_names.add(xy_stage)

                    if event.is_z_sequenced():
                        self.core.load_stage_sequence(z_stage, z_sequence)
                        hardware_sequences_in_progress.device_names.add(z_stage)

                    if event.is_config_group_sequenced():
                        for i in range(config.size()):
                            ps = config.get_setting(i)
                            device_name = ps.get_device_label()
                            prop_name = ps.get_property_name()

                            if prop_sequences.get(i).size() > 0:
                                self.core.load_property_sequence(device_name, prop_name, prop_sequences.get(i))
                                hardware_sequences_in_progress.property_names.add(prop_name)
                                hardware_sequences_in_progress.property_device_names.add(device_name)

                    self.core.prepare_sequence_acquisition(self.core.get_camera_device())

                    # Compare to last event to see what needs to change
                    if self.last_event is not None and self.last_event.acquisition_ != event.acquisition_:
                        self.last_event = None  # Update all hardware if switching to a new acquisition

            # Z stage
            loop_hardware_command_retries(lambda: move_z_device(event), "Moving Z device")
            # Other stage devices
            loop_hardware_command_retries(lambda: move_other_stage_devices(event), "Moving other stage devices")
            # XY Stage
            loop_hardware_command_retries(lambda: move_xy_stage(event), "Moving XY stage")
            # Channels
            loop_hardware_command_retries(lambda: change_channels(event), "Changing channels")
            # Camera exposure
            loop_hardware_command_retries(lambda: change_exposure(event), "Changing exposure")
            # SLM
            loop_hardware_command_retries(lambda: set_slm_pattern(event), "Setting SLM pattern")
            # Arbitrary Properties
            loop_hardware_command_retries(lambda: change_additional_properties(event), "Changing additional properties")
            # Keep track of last event
            self.last_event = event if event.get_sequence() is None else event.get_sequence()[-1]
        except:
            traceback.print_exc()
            raise HardwareControlException("Error executing event")

    def get_current_date_and_time(self):
        return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    def is_sequencable(self, previous_events, next_event, new_seq_length):
        try:
            if next_event.is_acquisition_sequence_end_event() or next_event.is_acquisition_finished_event():
                return False

            previous_event = previous_events[-1]

            # check all properties in group
            if previous_event.get_config_preset() is not None and next_event.get_config_preset() is not None and \
                    previous_event.get_config_preset() != next_event.get_config_preset():
                # check all properties in the channel
                config1 = self.core.get_config_data(previous_event.get_config_group(),
                                                    previous_event.get_config_preset())
                config2 = self.core.get_config_data(next_event.get_config_group(), next_event.get_config_preset())
                for i in range(config1.size()):
                    ps1 = config1.get_setting(i)
                    device_name = ps1.get_device_label()
                    prop_name = ps1.get_property_name()
                    prop_value1 = ps1.get_property_value()
                    ps2 = config2.get_setting(i)
                    prop_value2 = ps2.get_property_value()
                    if prop_value1 != prop_value2:
                        if not self.core.is_property_sequenceable(device_name, prop_name):
                            return False
                        if self.core.get_property_sequence_max_length(device_name, prop_name) < new_seq_length:
                            return False

            # TODO check for arbitrary additional properties in the acq event for being sequencable

            # z stage
            if previous_event.get_z_position() is not None and next_event.get_z_position() is not None and \
                    previous_event.get_z_position() != next_event.get_z_position():
                if not self.core.is_stage_sequenceable(self.core.get_focus_device()):
                    return False
                if new_seq_length > self.core.get_stage_sequence_max_length(self.core.get_focus_device()):
                    return False

            # arbitrary z stages
            # TODO implement sequences along arbitrary other stage devices
            for stage_device in previous_event.get_stage_device_names():
                return False

            # xy stage
            if (previous_event.get_x_position() is not None and next_event.get_x_position() is not None and
                previous_event.get_x_position() != next_event.get_x_position()) or \
                    (previous_event.get_y_position() is not None and next_event.get_y_position() is not None and
                     previous_event.get_y_position() != next_event.get_y_position()):
                if not self.core.is_xy_stage_sequenceable(self.core.get_xy_stage_device()):
                    return False
                if new_seq_length > self.core.get_xy_stage_sequence_max_length(self.core.get_xy_stage_device()):
                    return False

            if previous_event.get_camera_device_name() is None:
                # Using the Core-Camera, the default

                # camera exposure
                if previous_event.get_exposure() is not None and next_event.get_exposure() is not None and \
                        previous_event.get_exposure() != next_event.get_exposure() and \
                        not self.core.is_exposure_sequenceable(self.core.get_camera_device()):
                    return False
                if self.core.is_exposure_sequenceable(self.core.get_camera_device()) and \
                        new_seq_length > self.core.get_exposure_sequence_max_length(self.core.get_camera_device()):
                    return False

            # If there is a nonzero delay between events, then its not sequencable
            if previous_event.get_t_index() is not None and next_event.get_t_index() is not None and \
                    previous_event.get_t_index() != next_event.get_t_index():
                if previous_event.get_minimum_start_time_absolute() is not None and \
                        next_event.get_minimum_start_time_absolute() is not None and \
                        previous_event.get_minimum_start_time_absolute() != next_event.get_minimum_start_time_absolute():
                    return False

            return True
        except Exception as ex:
            raise RuntimeError(ex)

    def merge_sequence_event(self, event_list):
        if len(event_list) == 1:
            return event_list[0]
        return AcquisitionEvent(event_list[0].acquisition_, event_list)

