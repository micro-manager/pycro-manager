from pycromanager import JavaClass, Core


tester = JavaClass('org.micromanager.acquisition.internal.acqengjcompat.speedtest.SpeedTest')
pass

dir = r'C:\Users\henry\Desktop\data'
name = r'speed\test'
core = Core()
num_time_points = 1000
show_viewer = True

output_dir = tester.run_speed_test(dir, name, core, num_time_points, show_viewer)
print(output_dir)
pass