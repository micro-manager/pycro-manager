from collections import namedtuple
import json
from pycromanager.acquisition.acq_eng_py.main.acq_eng_metadata import AcqEngMetadata

class AcquisitionEvent:
    class SpecialFlag:
        ACQUISITION_FINISHED = "AcqusitionFinished"
        ACQUISITION_SEQUENCE_END = "AcqusitionSequenceEnd"

    def __init__(self, acq, sequence=None):
        self.acquisition_ = acq
        self.axisPositions_ = {}
        self.camera_ = None
        self.timeout_ms_ = None
        self.configGroup_ = None
        self.configPreset_ = None
        self.exposure_ = None
        self.miniumumStartTime_ms_ = None
        self.zPosition_ = None
        self.xPosition_ = None
        self.yPosition_ = None
        self.stageCoordinates_ = {}
        self.stageDeviceNamesToAxisNames_ = {}
        self.tags_ = {}
        self.acquireImage_ = None
        self.slmImage_ = None
        self.properties_ = set()
        self.sequence_ = None
        self.xySequenced_ = False
        self.zSequenced_ = False
        self.exposureSequenced_ = False
        self.configGroupSequenced_ = False
        self.specialFlag_ = None

        if sequence:
            self.acquisition_ = sequence[0].acquisition_
            self.miniumumStartTime_ms_ = sequence[0].miniumumStartTime_ms_
            self.sequence_ = list(sequence)
            zPosSet = set()
            xPosSet = set()
            yPosSet = set()
            exposureSet = set()
            configSet = set()
            for event in self.sequence_:
                if event.zPosition_:
                    zPosSet.add(event.get_z_position())
                if event.xPosition_:
                    xPosSet.add(event.get_x_position())
                if event.yPosition_:
                    yPosSet.add(event.get_y_position())
                if event.exposure_:
                    exposureSet.add(event.get_exposure())
                if event.configPreset_:
                    configSet.add(event.get_config_preset())
            self.exposureSequenced_ = len(exposureSet) > 1
            self.configGroupSequenced_ = len(configSet) > 1
            self.xySequenced_ = len(xPosSet) > 1 and len(yPosSet) > 1
            self.zSequenced_ = len(zPosSet) > 1
            if sequence[0].exposure_ and not self.exposureSequenced_:
                self.exposure_ = sequence[0].exposure_


    def copy(self):
        e = AcquisitionEvent(self.acquisition_)
        e.axisPositions_ = self.axisPositions_.copy()
        e.configPreset_ = self.configPreset_
        e.configGroup_ = self.configGroup_
        e.stageCoordinates_ = self.stageCoordinates_.copy()
        e.stageDeviceNamesToAxisNames_ = self.stageDeviceNamesToAxisNames_.copy()
        e.xPosition_ = self.xPosition_
        e.yPosition_ = self.yPosition_
        e.miniumumStartTime_ms_ = self.miniumumStartTime_ms_
        e.slmImage_ = self.slmImage_
        e.acquireImage_ = self.acquireImage_
        e.properties_ = set(self.properties_)
        e.camera_ = self.camera_
        e.timeout_ms_ = self.timeout_ms_
        e.setTags(self.tags_)  # Assuming setTags is a method in the class
        return e

    @staticmethod
    def event_to_json(e):
        data = {}

        if e.isAcquisitionFinishedEvent():
            data["special"] = "acquisition-end"
            return json.dumps(data)
        elif e.isAcquisitionSequenceEndEvent():
            data["special"] = "sequence-end"
            return json.dumps(data)

        if e.miniumumStartTime_ms_:
            data["min_start_time"] = e.miniumumStartTime_ms_ / 1000

        if e.hasConfigGroup():
            data["config_group"] = [e.configGroup_, e.configPreset_]

        if e.exposure_:
            data["exposure"] = e.exposure_

        if e.slmImage_:
            data["slm_pattern"] = e.slmImage_

        if e.timeout_ms_:
            data["timeout_ms"] = e.timeout_ms_

        axes = {axis: e.axisPositions_[axis] for axis in e.axisPositions_}
        if axes:
            data["axes"] = axes

        stage_positions = [[stageDevice, e.getStageSingleAxisStagePosition(stageDevice)] for stageDevice in e.getStageDeviceNames()]
        if stage_positions:
            data["stage_positions"] = stage_positions

        if e.zPosition_:
            data["z"] = e.zPosition_

        if e.xPosition_:
            data["x"] = e.xPosition_

        if e.yPosition_:
            data["y"] = e.yPosition_

        if e.camera_:
            data["camera"] = e.camera_

        if e.getTags() and e.getTags():  # Assuming getTags is a method in the class
            data["tags"] = {key: value for key, value in e.getTags().items()}

        props = [[t.dev, t.prop, t.val] for t in e.properties_]
        if props:
            data["properties"] = props

        return json.dumps(data)

    @staticmethod
    def event_from_json(data, acq):
        if "special" in data:
            if data["special"] == "acquisition-end":
                return AcquisitionEvent.createAcquisitionFinishedEvent(acq)
            elif data["special"] == "sequence-end":
                return AcquisitionEvent.createAcquisitionSequenceEndEvent(acq)

        event = AcquisitionEvent(acq)

        if "axes" in data:
            for axisLabel, value in data["axes"].items():
                event.axisPositions_[axisLabel] = value

        if "min_start_time" in data:
            event.miniumumStartTime_ms_ = int(data["min_start_time"] * 1000)

        if "timeout" in data:
            event.timeout_ms_ = data["timeout"]

        if "config_group" in data:
            event.configGroup_ = data["config_group"][0]
            event.configPreset_ = data["config_group"][1]

        if "exposure" in data:
            event.exposure_ = data["exposure"]

        if "timeout_ms" in data:
            event.slmImage_ = data["timeout_ms"]

        if "stage_positions" in data:
            for stagePos in data["stage_positions"]:
                event.setStageCoordinate(stagePos[0], stagePos[1])

        if "z" in data:
            event.zPosition_ = data["z"]

        if "stage" in data:
            deviceName = data["stage"]["device_name"]
            position = data["stage"]["position"]
            event.axisPositions_[deviceName] = position
            if "axis_name" in data["stage"]:
                axisName = data["stage"]["axis_name"]
                event.stageDeviceNamesToAxisNames_[deviceName] = axisName

        # # Assuming XYTiledAcquisition is a class and AcqEngMetadata is a class or module with constants
        # if isinstance(event.acquisition_, XYTiledAcquisition):
        #     posIndex = event.acquisition_.getPixelStageTranslator().getPositionIndices(
        #         [int(event.axisPositions_[AcqEngMetadata.AXES_GRID_ROW])],
        #         [int(event.axisPositions_[AcqEngMetadata.AXES_GRID_COL])])[0]
        #     xyPos = event.acquisition_.getPixelStageTranslator().getXYPosition(posIndex).getCenter()
        #     event.xPosition_ = xyPos.x
        #     event.yPosition_ = xyPos.y

        if "x" in data:
            event.xPosition_ = data["x"]

        if "y" in data:
            event.yPosition_ = data["y"]

        if "slm_pattern" in data:
            event.slmImage_ = data["slm_pattern"]

        if "camera" in data:
            event.camera_ = data["camera"]

        if "tags" in data:
            tags = {key: value for key, value in data["tags"].items()}
            event.setTags(tags)

        if "properties" in data:
            for trip in data["properties"]:
                t = ThreeTuple(trip[0], trip[1], trip[2])
                event.properties_.add(t)

        return event

    def to_json(self):
        if self.sequence_:
            events = [self.event_to_json(e) for e in self.sequence_]
            return json.dumps({"events": events})
        else:
            return self.event_to_json(self)

    @staticmethod
    def from_json(data, acq):
        if "events" not in data:
            return AcquisitionEvent.event_from_json(data, acq)
        else:
            sequence = [AcquisitionEvent.event_from_json(item, acq) for item in data["events"]]
            return AcquisitionEvent(sequence)

    def get_camera_device_name(self):
        return self.camera_

    def set_camera_device_name(self, camera):
        self.camera_ = camera

    def get_additional_properties(self):
        return [(t.dev, t.prop, t.val) for t in self.properties_]

    def should_acquire_image(self):
        if self.sequence_:
            return True
        return self.configPreset_ is not None or len(self.axisPositions_) > 0

    def has_config_group(self):
        return self.configPreset_ is not None and self.configGroup_ is not None

    def get_config_preset(self):
        return self.configPreset_

    def get_config_group(self):
        return self.configGroup_

    def set_config_preset(self, config):
        self.configPreset_ = config

    def set_config_group(self, group):
        self.configGroup_ = group

    def get_exposure(self):
        return self.exposure_

    def set_exposure(self, exposure):
        self.exposure_ = exposure

    def set_property(self, device, property, value):
        self.properties_.add(ThreeTuple(device, property, value))

    def set_minimum_start_time(self, l):
        self.miniumumStartTime_ms_ = l

    def get_defined_axes(self):
        return set(self.axisPositions_.keys())

    def set_axis_position(self, label, position):
        if position is None:
            raise Exception("Cannot set axis position to null")
        self.axisPositions_[label] = position

    def set_stage_coordinate(self, deviceName, v, axisName=None):
        self.stageCoordinates_[deviceName] = v
        self.stageDeviceNamesToAxisNames_[deviceName] = deviceName if axisName is None else axisName

    def get_stage_single_axis_stage_position(self, deviceName):
        return self.stageCoordinates_.get(deviceName)

    def get_axis_positions(self):
        return self.axisPositions_

    def get_axis_position(self, label):
        return self.axisPositions_.get(label)

    def get_timeout_ms(self):
        return self.timeout_ms_

    def set_time_index(self, index):
        self.set_axis_position(AcqEngMetadata.TIME_AXIS, index)

    def set_channel_name(self, name):
        self.set_axis_position(AcqEngMetadata.CHANNEL_AXIS, name)

    def get_slm_image(self):
        return self.slmImage_

    def set_z(self, index, position):
        if index is not None:
            self.set_axis_position(AcqEngMetadata.Z_AXIS, index)
        self.zPosition_ = position

    def get_t_index(self):
        return self.get_axis_position(AcqEngMetadata.TIME_AXIS)

    def get_z_index(self):
        return self.get_axis_position(AcqEngMetadata.Z_AXIS)

    def get_device_axis_name(self, deviceName):
        if deviceName not in self.stageDeviceNamesToAxisNames_:
            raise Exception(f"No axis name for device {deviceName}. call setStageCoordinate first")
        return self.stageDeviceNamesToAxisNames_[deviceName]

    def get_stage_device_names(self):
        return set(self.stageDeviceNamesToAxisNames_.keys())

    @staticmethod
    def create_acquisition_finished_event(acq):
        evt = AcquisitionEvent(acq)
        evt.specialFlag_ = AcquisitionEvent.SpecialFlag.ACQUISITION_FINISHED
        return evt

    def is_acquisition_finished_event(self):
        return self.specialFlag_ == AcquisitionEvent.SpecialFlag.ACQUISITION_FINISHED

    @staticmethod
    def create_acquisition_sequence_end_event(acq):
        evt = AcquisitionEvent(acq)
        evt.specialFlag_ = AcquisitionEvent.SpecialFlag.ACQUISITION_SEQUENCE_END
        return evt

    def is_acquisition_sequence_end_event(self):
        return self.specialFlag_ == AcquisitionEvent.SpecialFlag.ACQUISITION_SEQUENCE_END

    def get_z_position(self):
        return self.zPosition_

    def get_minimum_start_time_absolute(self):
        if self.miniumumStartTime_ms_ is None:
            return None
        return self.acquisition_.get_start_time_ms() + self.miniumumStartTime_ms_

    def get_sequence(self):
        return self.sequence_

    def is_exposure_sequenced(self):
        return self.exposureSequenced_

    def is_config_group_sequenced(self):
        return self.configGroupSequenced_

    def is_xy_sequenced(self):
        return self.xySequenced_

    def is_z_sequenced(self):
        return self.zSequenced_

    def get_x_position(self):
        return self.xPosition_

    def get_camera_image_counts(self, default_camera_device_name):
        """
        Get the number of images to be acquired on each camera in a sequence event.
        For a non-sequence event, the number of images is 1, and the camera is the core camera.
        This is passed in as an argument in order to avoid this class talking to the core directly.

        Args:
            default_camera_device_name (str): Default camera device name.

        Returns:
            defaultdict: Dictionary containing the camera device names as keys and image counts as values.
        """
        # Figure out how many images on each camera and start sequence with appropriate number on each
        camera_image_counts = {}
        camera_device_names = set()
        if self.get_sequence() is None:
            camera_image_counts[default_camera_device_name] = 1
            return camera_image_counts

        for event in self.get_sequence():
            camera_device_names.add(event.get_camera_device_name() if event.get_camera_device_name() is not None else
                                    default_camera_device_name)
        if None in camera_device_names:
            camera_device_names.remove(None)
            camera_device_names.add(default_camera_device_name)

        for camera_device_name in camera_device_names:
            camera_image_counts[camera_device_name] = sum(1 for event in self.get_sequence()
                                                          if event.get_camera_device_name() == camera_device_name)

            if len(camera_device_names) == 1 and camera_device_name == default_camera_device_name:
                camera_image_counts[camera_device_name] = len(self.get_sequence())

        return camera_image_counts

    def get_y_position(self):
        return self.yPosition_

    def get_position_name(self):
        axisPosition_ = self.get_axis_position(AcqEngMetadata.POSITION_AXIS)
        if isinstance(axisPosition_, str):
            return axisPosition_
        return None

    def set_x(self, x):
        self.xPosition_ = x

    def set_y(self, y):
        self.yPosition_ = y

    def set_tags(self, tags):
        self.tags_.clear()
        if tags:
            self.tags_.update(tags)

    def get_tags(self):
        return dict(self.tags_)

    def __str__(self):
        if self.specialFlag_ == AcquisitionEvent.SpecialFlag.AcquisitionFinished:
            return "Acq finished event"
        elif self.specialFlag_ == AcquisitionEvent.SpecialFlag.AcquisitionSequenceEnd:
            return "Acq sequence end event"

        builder = []
        for deviceName in self.stageDeviceNamesToAxisNames_.keys():
            builder.append(f"\t{deviceName}: {self.get_stage_single_axis_stage_position(deviceName)}")

        if self.zPosition_ is not None:
            builder.append(f"z {self.zPosition_}")
        if self.xPosition_ is not None:
            builder.append(f"x {self.xPosition_}")
        if self.yPosition_ is not None:
            builder.append(f"y {self.yPosition_}")

        for axis in self.axisPositions_.keys():
            builder.append(f"\t{axis}: {self.axisPositions_[axis]}")

        if self.camera_ is not None:
            builder.append(f"\t{self.camera_}: {self.camera_}")

        return ' '.join(builder)


ThreeTuple = namedtuple('ThreeTuple', ['dev', 'prop', 'val'])
