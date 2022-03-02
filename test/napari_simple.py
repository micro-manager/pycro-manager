from pycromanager import Acquisition, multi_d_acquisition_events, start_headless
import napari

# Optional: Launch headless mode, which means Micro-Manager does
# not already need to be open
# mm_app_path = 'C:/Program Files/Micro-Manager-2.0gamma'
# config_file = mm_app_path + "/MMConfig_demo.cfg"
# start_headless(mm_app_path, config_file)


acq = Acquisition(directory=r"C:\Users\henry\Desktop\data", name="tcz_acq",
                  show_display='napari')
events = multi_d_acquisition_events(num_time_points=8, time_interval_s=2,
                                 z_start=0, z_end=6, z_step=0.7,)
acq.acquire(events)
acq.mark_finished()

napari.run()