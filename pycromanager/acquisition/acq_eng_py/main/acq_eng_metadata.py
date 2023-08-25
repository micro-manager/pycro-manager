import datetime
import json
import traceback
import numpy as np

class AcqEngMetadata:

    CHANNEL_GROUP = "ChannelGroup"
    CORE_AUTOFOCUS_DEVICE = "Core-Autofocus"
    CORE_CAMERA = "Core-Camera"
    CORE_GALVO = "Core-Galvo"
    CORE_IMAGE_PROCESSOR = "Core-ImageProcessor"
    CORE_SLM = "Core-SLM"
    CORE_SHUTTER = "Core-Shutter"
    WIDTH = "Width"
    HEIGHT = "Height"
    PIX_SIZE = "PixelSize_um"
    POS_NAME = "PositionName"
    X_UM_INTENDED = "XPosition_um_Intended"
    Y_UM_INTENDED = "YPosition_um_Intended"
    Z_UM_INTENDED = "ZPosition_um_Intended"
    GENERIC_UM_INTENDED_SUFFIX = "Position_um_Intended"
    X_UM = "XPosition_um"
    Y_UM = "YPosition_um"
    Z_UM = "ZPosition_um"
    EXPOSURE = "Exposure"
    CHANNEL_NAME = "Channel"
    ZC_ORDER = "SlicesFirst"  # this is called ZCT in the functions
    TIME = "Time"
    DATE_TIME = "DateAndTime"
    SAVING_PREFIX = "Prefix"
    INITIAL_POS_LIST = "InitialPositionList"
    TIMELAPSE_INTERVAL = "Interval_ms"
    PIX_TYPE = "PixelType"
    BIT_DEPTH = "BitDepth"
    ELAPSED_TIME_MS = "ElapsedTime-ms"
    Z_STEP_UM = "z-step_um"
    EXPLORE_ACQUISITION = "ExploreAcquisition"
    AXES_GRID_COL = "column"
    AXES_GRID_ROW = "row"
    OVERLAP_X = "GridPixelOverlapX"
    OVERLAP_Y = "GridPixelOverlapY"
    AFFINE_TRANSFORM = "AffineTransform"
    PIX_TYPE_GRAY8 = "GRAY8"
    PIX_TYPE_GRAY16 = "GRAY16"
    CORE_XYSTAGE = "Core-XYStage"
    CORE_FOCUS = "Core-Focus"
    AXES = "Axes"
    CHANNEL_AXIS = "channel"
    TIME_AXIS = "time"
    Z_AXIS = "z"
    POSITION_AXIS = "position"
    TAGS = "tags"
    ACQUISITION_EVENT = "Event"

    @staticmethod
    def add_image_metadata(core, tags, event, elapsed_ms, exposure):
        try:
            AcqEngMetadata.set_pixel_size_um(tags, core.get_pixel_size_um())

            # Date and time
            AcqEngMetadata.set_elapsed_time_ms(tags, elapsed_ms)
            AcqEngMetadata.set_image_time(tags, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S -'))

            # Info about all hardware that the core specifically knows about
            AcqEngMetadata.create_axes(tags)

            # Axes positions
            for s in event.get_defined_axes():
                AcqEngMetadata.set_axis_position(tags, s, event.get_axis_position(s))

            # XY Stage Positions
            if event.get_x_position() is not None and event.get_y_position() is not None:
                AcqEngMetadata.set_stage_x_intended(tags, event.get_x_position())
                AcqEngMetadata.set_stage_y_intended(tags, event.get_y_position())
            if event.get_position_name() is not None:
                AcqEngMetadata.set_position_name(tags, event.get_position_name())

            if event.get_z_position() is not None:
                AcqEngMetadata.set_stage_z_intended(tags, event.get_z_position())
            elif event.get_stage_single_axis_stage_position(core.get_focus_device()) is not None:
                AcqEngMetadata.set_stage_z_intended(tags,
                                                    event.get_stage_single_axis_stage_position(core.get_focus_device()))

            for name in event.get_stage_device_names():
                if name != core.get_focus_device():
                    AcqEngMetadata.set_stage_position_intended(tags, name,
                                                               event.get_stage_single_axis_stage_position(name))

            if event.get_sequence() is not None:
                AcqEngMetadata.add_acquisition_event(tags, event)

            AcqEngMetadata.set_exposure(tags, exposure)

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError("Problem adding image metadata")

    @staticmethod
    def add_acquisition_event(tags, event):
        tags[AcqEngMetadata.ACQUISITION_EVENT] = event.toJSON()


    @staticmethod
    def make_summary_metadata(core, acq):
        summary = json.loads("{}")

        AcqEngMetadata.set_acq_date(summary, AcqEngMetadata.get_current_date_and_time())

        # General information the core-camera
        byte_depth = int(core.get_bytes_per_pixel())
        if byte_depth == 0:
            raise RuntimeError("Camera byte depth cannot be zero")
        AcqEngMetadata.set_pixel_type_from_byte_depth(summary, byte_depth)
        AcqEngMetadata.set_pixel_size_um(summary, core.get_pixel_size_um())

        # Info about core devices
        try:
            AcqEngMetadata.set_core_xy(summary, core.get_xy_stage_device())
            AcqEngMetadata.set_core_focus(summary, core.get_focus_device())
            AcqEngMetadata.set_core_autofocus(summary, core.get_auto_focus_device())
            AcqEngMetadata.set_core_camera(summary, core.get_camera_device())
            AcqEngMetadata.set_core_galvo(summary, core.get_galvo_device())
            AcqEngMetadata.set_core_image_processor(summary, core.get_image_processor_device())
            AcqEngMetadata.set_core_slm(summary, core.get_slm_device())
            AcqEngMetadata.set_core_shutter(summary, core.get_shutter_device())
        except Exception as e:
            raise RuntimeError("couldn't get info from core about devices")

        # TODO restore
        # # Affine transform
        # if AffineTransformUtils.isAffineTransformDefined():
        #     at = AffineTransformUtils.getAffineTransform(0, 0)
        #     AcqEngMetadata.setAffineTransformString(summary, AffineTransformUtils.transformToString(at))
        # else:
        #     AcqEngMetadata.setAffineTransformString(summary, "Undefined")

        return summary
    

    @staticmethod
    def get_current_date_and_time():
        return datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    @staticmethod
    def get_indices(image_label):
        s = image_label.split("_")
        return [int(i) for i in s]

    @staticmethod
    def copy(map):
        return json.loads(json.dumps(map))

    @staticmethod
    def set_core_xy(map, xy_name):
        map[AcqEngMetadata.CORE_XYSTAGE] = xy_name

    @staticmethod
    def has_core_xy(map):
        return AcqEngMetadata.CORE_XYSTAGE in map

    @staticmethod
    def get_core_xy(map):
        if AcqEngMetadata.CORE_XYSTAGE in map:
            return map[AcqEngMetadata.CORE_XYSTAGE]
        else:
            raise ValueError("Missing core xy stage tag")

    @staticmethod
    def set_core_focus(map, z_name):
        map[AcqEngMetadata.CORE_FOCUS] = z_name

    @staticmethod
    def has_core_focus(map):
        return AcqEngMetadata.CORE_FOCUS in map

    @staticmethod
    def get_core_focus(map):
        if AcqEngMetadata.CORE_FOCUS in map:
            return map[AcqEngMetadata.CORE_FOCUS]
        else:
            raise ValueError("Missing core focus tag")

    @staticmethod
    def set_acq_date(map, date_time):
        map[AcqEngMetadata.DATE_TIME] = date_time

    @staticmethod
    def is_explore_acq(summary_metadata):
        if AcqEngMetadata.EXPLORE_ACQUISITION in summary_metadata:
            return summary_metadata[AcqEngMetadata.EXPLORE_ACQUISITION]
        else:
            raise ValueError("Missing explore tag")

    @staticmethod
    def set_explore_acq(summary_metadata, b):
        summary_metadata[AcqEngMetadata.EXPLORE_ACQUISITION] = b

    @staticmethod
    def has_acq_date(map):
        return AcqEngMetadata.DATE_TIME in map

    @staticmethod
    def get_acq_date(map):
        if AcqEngMetadata.DATE_TIME in map:
            return map[AcqEngMetadata.DATE_TIME]
        else:
            raise ValueError("Missing Acq dat time tag")

    @staticmethod
    def set_bit_depth(map, bit_depth):
        map[AcqEngMetadata.BIT_DEPTH] = bit_depth

    @staticmethod
    def has_bit_depth(map):
        return AcqEngMetadata.BIT_DEPTH in map

    @staticmethod
    def get_bit_depth(map):
        try:
            return map[AcqEngMetadata.BIT_DEPTH]
        except KeyError:
            raise ValueError("Missing bit depth tag")

    @staticmethod
    def set_width(map, width):
        map[AcqEngMetadata.WIDTH] = width

    @staticmethod
    def has_width(map):
        return AcqEngMetadata.WIDTH in map

    @staticmethod
    def get_width(map):
        try:
            return map[AcqEngMetadata.WIDTH]
        except KeyError:
            raise ValueError("Image width tag missing")

    @staticmethod
    def set_height(map, height):
        map[AcqEngMetadata.HEIGHT] = height

    @staticmethod
    def has_height(map):
        return AcqEngMetadata.HEIGHT in map

    @staticmethod
    def get_height(map):
        try:
            return map[AcqEngMetadata.HEIGHT]
        except KeyError:
            raise ValueError("Height missing from image tags")

    @staticmethod
    def set_position_name(map, position_name):
        map[AcqEngMetadata.POS_NAME] = position_name

    @staticmethod
    def has_position_name(map):
        return AcqEngMetadata.POS_NAME in map

    @staticmethod
    def get_position_name(map):
        try:
            return map[AcqEngMetadata.POS_NAME]
        except KeyError:
            raise ValueError("Missing position name tag")

    @staticmethod
    def set_pixel_type_from_string(map, pixel_type):
        map[AcqEngMetadata.PIX_TYPE] = pixel_type

    @staticmethod
    def set_pixel_type_from_byte_depth(map, depth):
        try:
            if depth == 1:
                map[AcqEngMetadata.PIX_TYPE] = AcqEngMetadata.PIX_TYPE_GRAY8
            elif depth == 2:
                map[AcqEngMetadata.PIX_TYPE] = AcqEngMetadata.PIX_TYPE_GRAY16
            elif depth == 4:
                map[AcqEngMetadata.PIX_TYPE] = AcqEngMetadata.PIX_TYPE_RGB32
        except KeyError:
            raise ValueError("Couldn't set pixel type")

    @staticmethod
    def has_pixel_type(map):
        return AcqEngMetadata.PIX_TYPE in map

    @staticmethod
    def get_pixel_type(map):
        try:
            return map[AcqEngMetadata.PIX_TYPE]
        except KeyError:
            raise ValueError("Missing pixel type tag")

    @staticmethod
    def get_bytes_per_pixel(map):
        if AcqEngMetadata.is_gray8(map):
            return 1
        elif AcqEngMetadata.is_gray16(map):
            return 2
        elif AcqEngMetadata.is_rgb32(map):
            return 4
        else:
            return 0

    @staticmethod
    def get_number_of_components(map):
        pixel_type = AcqEngMetadata.get_pixel_type(map)
        if pixel_type == AcqEngMetadata.PIX_TYPE_GRAY8 or pixel_type == AcqEngMetadata.PIX_TYPE_GRAY16:
            return 1
        elif pixel_type == AcqEngMetadata.PIX_TYPE_RGB32:
            return 3
        else:
            raise ValueError("Invalid pixel type")

    @staticmethod
    def is_gray8(map):
        return AcqEngMetadata.get_pixel_type(map) == AcqEngMetadata.PIX_TYPE_GRAY8

    @staticmethod
    def is_gray16(map):
        return AcqEngMetadata.get_pixel_type(map) == AcqEngMetadata.PIX_TYPE_GRAY16

    @staticmethod
    def is_rgb32(map):
        return AcqEngMetadata.get_pixel_type(map) == AcqEngMetadata.PIX_TYPE_RGB32

    @staticmethod
    def is_gray(map):
        return AcqEngMetadata.is_gray8(map) or AcqEngMetadata.is_gray16(map)

    @staticmethod
    def is_rgb(map):
        return AcqEngMetadata.is_rgb32(map)

    @staticmethod
    def get_keys(md):
        n = len(md)
        key_array = [None] * n
        keys = md.keys()
        for i in range(n):
            key_array[i] = keys.next()
        return key_array

    @staticmethod
    def get_json_array_member(obj, key):
        try:
            return obj[key]
        except KeyError:
            raise ValueError("Missing JSONArray member")

    @staticmethod
    def set_image_time(map, time):
        try:
            map[AcqEngMetadata.TIME] = time
        except KeyError:
            raise ValueError("Couldn't set image time")

    @staticmethod
    def has_image_time(map):
        return AcqEngMetadata.TIME in map

    @staticmethod
    def get_image_time(map):
        try:
            return map[AcqEngMetadata.TIME]
        except KeyError:
            raise ValueError("Missing image time tag")

    @staticmethod
    def get_depth(tags):
        pixel_type = AcqEngMetadata.get_pixel_type(tags)
        if AcqEngMetadata.PIX_TYPE_GRAY8 in pixel_type:
            return 1
        elif AcqEngMetadata.PIX_TYPE_GRAY16 in pixel_type:
            return 2
        else:
            return 0

    @staticmethod
    def set_exposure(map, exp):
        try:
            map[AcqEngMetadata.EXPOSURE] = exp
        except KeyError:
            raise ValueError("Could not set exposure")

    @staticmethod
    def has_exposure(map):
        return AcqEngMetadata.EXPOSURE in map

    @staticmethod
    def get_exposure(map):
        try:
            return map[AcqEngMetadata.EXPOSURE]
        except KeyError:
            raise ValueError("Exposure tag missing")

    @staticmethod
    def set_pixel_size_um(map, val):
        try:
            map[AcqEngMetadata.PIX_SIZE] = val
        except KeyError:
            raise ValueError("Missing pixel size tag")

    @staticmethod
    def has_pixel_size_um(map):
        return AcqEngMetadata.PIX_SIZE in map

    @staticmethod
    def get_pixel_size_um(map):
        try:
            return map[AcqEngMetadata.PIX_SIZE]
        except KeyError:
            raise ValueError("Pixel size missing in metadata")

    @staticmethod
    def set_z_step_um(map, val):
        try:
            map[AcqEngMetadata.Z_STEP_UM] = val
        except KeyError:
            raise ValueError("Couldn't set z step tag")

    @staticmethod
    def has_z_step_um(map):
        return AcqEngMetadata.Z_STEP_UM in map

    @staticmethod
    def get_z_step_um(map):
        try:
            return map[AcqEngMetadata.Z_STEP_UM]
        except KeyError:
            raise ValueError("Z step metadata field missing")

    @staticmethod
    def set_z_position_um(map, val):
        try:
            map[AcqEngMetadata.Z_UM] = val
        except KeyError:
            raise ValueError("Couldn't set z position")

    @staticmethod
    def has_z_position_um(map):
        return AcqEngMetadata.Z_UM in map

    @staticmethod
    def get_z_position_um(map):
        try:
            return map[AcqEngMetadata.Z_UM]
        except KeyError:
            raise ValueError("Missing Z position tag")

    @staticmethod
    def set_elapsed_time_ms(map, val):
        try:
            map[AcqEngMetadata.ELAPSED_TIME_MS] = val
        except KeyError:
            raise ValueError("Couldn't set elapsed time")

    @staticmethod
    def has_elapsed_time_ms(map):
        return AcqEngMetadata.ELAPSED_TIME_MS in map

    @staticmethod
    def get_elapsed_time_ms(map):
        try:
            return map[AcqEngMetadata.ELAPSED_TIME_MS]
        except KeyError:
            raise RuntimeError("missing elapsed time tag")

    @staticmethod
    def set_interval_ms(map, val):
        map[AcqEngMetadata.TIMELAPSE_INTERVAL] = val

    @staticmethod
    def has_interval_ms(map):
        return AcqEngMetadata.TIMELAPSE_INTERVAL in map

    @staticmethod
    def get_interval_ms(map):
        try:
            return map[AcqEngMetadata.TIMELAPSE_INTERVAL]
        except KeyError:
            raise RuntimeError("Time interval missing from summary metadata")

    @staticmethod
    def set_zct_order(map, val):
        map[AcqEngMetadata.ZC_ORDER] = val

    @staticmethod
    def has_zct_order(map):
        return AcqEngMetadata.ZC_ORDER in map

    @staticmethod
    def get_zct_order(map):
        try:
            return map[AcqEngMetadata.ZC_ORDER]
        except KeyError:
            raise RuntimeError("Missing ZCT Tag")

    @staticmethod
    def set_affine_transform_string(summary_md, affine):
        summary_md[AcqEngMetadata.AFFINE_TRANSFORM] = affine

    @staticmethod
    def has_affine_transform_string(map):
        return AcqEngMetadata.AFFINE_TRANSFORM in map

    @staticmethod
    def get_affine_transform_string(summary_md):
        try:
            return summary_md[AcqEngMetadata.AFFINE_TRANSFORM]
        except KeyError:
            raise RuntimeError("Affine transform missing from summary metadata")

    @staticmethod
    def get_affine_transform(summary_md):
        try:
            return AcqEngMetadata.string_to_transform(summary_md[AcqEngMetadata.AFFINE_TRANSFORM])
        except KeyError:
            raise RuntimeError("Affine transform missing from summary metadata")

    @staticmethod
    def string_to_transform(s):
        if s == "Undefined":
            return None
        mat = [0] * 4
        vals = s.split("_")
        for i in range(4):
            mat[i] = float(vals[i])
        return AcqEngMetadata.AffineTransform(mat)

    @staticmethod
    def set_pixel_overlap_x(smd, overlap):
        smd[AcqEngMetadata.OVERLAP_X] = overlap

    @staticmethod
    def has_pixel_overlap_x(map):
        return AcqEngMetadata.OVERLAP_X in map

    @staticmethod
    def get_pixel_overlap_x(summary_md):
        try:
            return summary_md[AcqEngMetadata.OVERLAP_X]
        except KeyError:
            raise RuntimeError("Could not find pixel overlap in image tags")

    @staticmethod
    def set_pixel_overlap_y(smd, overlap):
        smd[AcqEngMetadata.OVERLAP_Y] = overlap

    @staticmethod
    def has_pixel_overlap_y(map):
        return AcqEngMetadata.OVERLAP_Y in map

    @staticmethod
    def get_pixel_overlap_y(summary_md):
        try:
            return summary_md[AcqEngMetadata.OVERLAP_Y]
        except KeyError:
            raise RuntimeError("Could not find pixel overlap in image tags")

    @staticmethod
    def set_stage_x_intended(smd, x):
        smd[AcqEngMetadata.X_UM_INTENDED] = x

    @staticmethod
    def has_stage_x_intended(map):
        return AcqEngMetadata.X_UM_INTENDED in map

    @staticmethod
    def get_stage_x_intended(smd):
        try:
            return smd[AcqEngMetadata.X_UM_INTENDED]
        except KeyError:
            raise RuntimeError("Could not get stage x")

    @staticmethod
    def set_stage_y_intended(smd, y):
        smd[AcqEngMetadata.Y_UM_INTENDED] = y

    @staticmethod
    def has_stage_y_intended(map):
        return AcqEngMetadata.Y_UM_INTENDED in map

    @staticmethod
    def get_stage_y_intended(smd):
        try:
            return smd[AcqEngMetadata.Y_UM_INTENDED]
        except KeyError:
            raise RuntimeError("Could not get stage y")

    @staticmethod
    def set_stage_z_intended(smd, y):
        smd[AcqEngMetadata.Z_UM_INTENDED] = y

    @staticmethod
    def has_stage_z_intended(map):
        return AcqEngMetadata.Z_UM_INTENDED in map

    @staticmethod
    def get_stage_z_intended(smd):
        try:
            return smd[AcqEngMetadata.Z_UM_INTENDED]
        except KeyError:
            raise RuntimeError("Could not get stage Z")

    @staticmethod
    def set_stage_position_intended(tags, name, stage_single_axis_stage_position):
        tags[name + AcqEngMetadata.GENERIC_UM_INTENDED_SUFFIX] = stage_single_axis_stage_position

    @staticmethod
    def set_stage_x(smd, x):
        smd[AcqEngMetadata.X_UM] = x

    @staticmethod
    def has_stage_x(map):
        return AcqEngMetadata.X_UM in map

    @staticmethod
    def get_stage_x(smd):
        try:
            return smd[AcqEngMetadata.X_UM]
        except KeyError:
            raise RuntimeError("Could not get stage x")

    @staticmethod
    def set_stage_y(smd, y):
        smd[AcqEngMetadata.Y_UM] = y

    @staticmethod
    def has_stage_y(map):
        return AcqEngMetadata.Y_UM in map

    @staticmethod
    def get_stage_y(smd):
        try:
            return smd[AcqEngMetadata.Y_UM]
        except KeyError:
            raise RuntimeError("Could not get stage y")

    @staticmethod
    def set_channel_group(summary, channel_group):
        summary[AcqEngMetadata.CHANNEL_GROUP] = channel_group

    @staticmethod
    def has_channel_group(map):
        return AcqEngMetadata.CHANNEL_GROUP in map

    @staticmethod
    def get_channel_group(summary):
        try:
            return summary[AcqEngMetadata.CHANNEL_GROUP]
        except KeyError:
            raise RuntimeError("Could not find Channel Group")

    @staticmethod
    def set_core_autofocus(summary, auto_focus_device):
        summary[AcqEngMetadata.CORE_AUTOFOCUS_DEVICE] = auto_focus_device

    @staticmethod
    def has_core_autofocus(summary):
        return AcqEngMetadata.CORE_AUTOFOCUS_DEVICE in summary

    @staticmethod
    def get_core_autofocus_device(summary):
        try:
            return summary[AcqEngMetadata.CORE_AUTOFOCUS_DEVICE]
        except KeyError:
            raise ValueError("Could not find autofocus device")

    @staticmethod
    def set_core_camera(summary, camera_device):
        summary[AcqEngMetadata.CORE_CAMERA] = camera_device

    @staticmethod
    def has_core_camera(summary):
        return AcqEngMetadata.CORE_CAMERA in summary

    @staticmethod
    def get_core_camera(summary):
        try:
            return summary[AcqEngMetadata.CORE_CAMERA]
        except KeyError:
            raise ValueError("Could not get core camera")

    @staticmethod
    def set_core_galvo(summary, galvo_device):
        summary[AcqEngMetadata.CORE_GALVO] = galvo_device

    @staticmethod
    def has_core_galvo(summary):
        return AcqEngMetadata.CORE_GALVO in summary

    @staticmethod
    def get_core_galvo(summary):
        try:
            return summary[AcqEngMetadata.CORE_GALVO]
        except KeyError:
            raise ValueError("Could not get core galvo")

    @staticmethod
    def set_core_image_processor(summary, image_processor_device):
        summary[AcqEngMetadata.CORE_IMAGE_PROCESSOR] = image_processor_device

    @staticmethod
    def has_core_image_processor(summary):
        return AcqEngMetadata.CORE_IMAGE_PROCESSOR in summary

    @staticmethod
    def get_core_image_processor(summary):
        try:
            return summary[AcqEngMetadata.CORE_IMAGE_PROCESSOR]
        except KeyError:
            raise ValueError("Could not find core image processor")

    @staticmethod
    def set_core_slm(summary, slm_device):
        summary[AcqEngMetadata.CORE_SLM] = slm_device

    @staticmethod
    def has_core_slm(summary):
        return AcqEngMetadata.CORE_SLM in summary

    @staticmethod
    def get_core_slm(summary):
        try:
            return summary[AcqEngMetadata.CORE_SLM]
        except KeyError:
            raise ValueError("Could not find core slm")

    @staticmethod
    def set_core_shutter(summary, shutter_device):
        summary[AcqEngMetadata.CORE_SHUTTER] = shutter_device

    @staticmethod
    def has_core_shutter(summary):
        return AcqEngMetadata.CORE_SHUTTER in summary

    @staticmethod
    def get_core_shutter(summary):
        try:
            return summary[AcqEngMetadata.CORE_SHUTTER]
        except KeyError:
            raise ValueError("Could not find core shutter")

    @staticmethod
    def create_axes(tags):
        tags[AcqEngMetadata.AXES] = {}

    @staticmethod
    def get_axes(tags):
        try:
            axes = tags[AcqEngMetadata.AXES]
            axes_map = {}
            for key in axes:
                axes_map[key] = axes[key]
            return axes_map
        except KeyError:
            raise ValueError("Could not create axes")

    @staticmethod
    def get_axes_as_json(axes):
        try:
            axes_json = {}
            for key in axes:
                axes_json[key] = axes[key]
            return axes_json
        except KeyError:
            raise ValueError("Could not convert axes to JSON")

    @staticmethod
    def set_axis_position(tags, axis, position):
        if position is None:
            if AcqEngMetadata.has_axis(tags, axis):
                del tags[AcqEngMetadata.AXES][axis]
                return
        if not isinstance(position, (str, int, np.int64, np.int32)):
            raise ValueError("position must be String or Integer")
        tags[AcqEngMetadata.AXES][axis] = position

    @staticmethod
    def has_axis(tags, axis):
        try:
            return axis in tags[AcqEngMetadata.AXES]
        except KeyError:
            raise ValueError("Axes not present in metadata")

    @staticmethod
    def get_axis_position(tags, axis):
        try:
            return tags[AcqEngMetadata.AXES][axis]
        except KeyError:
            raise ValueError("Could not create axes")