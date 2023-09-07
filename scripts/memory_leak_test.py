from pycromanager import ZMQRemoteMMCoreJ, Studio

core = ZMQRemoteMMCoreJ()
studio = Studio()

for i in range(20):
    core.start_sequence_acquisition(400, 0, True)
    while core.get_remaining_image_count() > 0 or core.is_sequence_running():
        if core.get_remaining_image_count() > 0:
            tagged = core.pop_next_tagged_image()
            studio.data().convert_tagged_image(tagged)
        else:
            core.sleep(5)