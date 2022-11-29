from pycromanager import Acquisition, multi_d_acquisition_events, start_headless, Core
import threading


def snap_image():
    while True:
        core = Core()
        try:
            core.snap_image()
            image = core.get_tagged_image()
        except Exception as e:
            print("snap image error: %s" % e)
            import traceback
            traceback.print_exception(e)


if __name__ == '__main__':
    # mm_app_path = '/Applications/Micro-Manager-2.0.0-gamma1'
    # config_file = '/Applications/Micro-Manager-2.0.0-gamma1/MMConfig_demo.cfg'
    #
    # start_headless(mm_app_path, config_file, timeout=10000)

    # bridge = Bridge(timeout=1000)
    core = Core()
    print(core.get_version_info())

    t = threading.Thread(target=snap_image, args=())
    t.start()

    while True:
        tm = core.get_exposure()
        print("Exposure %d" % tm)