"""
Streaming data from micro-manager to napari: PSF Viewer

developed by Wiebke Jahr, Danzl lab, IST Austria, (c) 2020
latest version on github: https://github.com/wiebkejahr/pycro-manager

If you use this tool, please cite:
pycro-manager: Pinkard, H., Stuurman, N., Ivanov, I.E. et al. Pycro-Manager: open-source software for customized and reproducible microscope control. Nat Methods (2021). https://doi.org/10.1038/s41592-021-01087-6
napari: napari contributors (2019). napari: a multi-dimensional image viewer for python. https://doi.org/10.5281/zenodo.3555620

This notebook shows how to acquire data using micromanager, then use pycro-manager to stream it to napari. Buttons to start and stop data acquisition are added to the napari window using the magic-gui package. In this example, the data displayed in napari is resliced to get a live PSF viewer. However, reslicing is only a small example for the data analysis possible using napari.

Here are two videos showing the PSF viewer in action:
https://www.dropbox.com/sh/fpr2nitlhfb68od/AAArXxDLclfXWhsyF0x_fP7Ja?dl=0

    PSFViewer-ExternalStageControl_1080p.mp4: z-stage controlled via micromanager
    PSFViewer-InternalStageControl_1080p.mp4: z-stage controlled via external DAQ control

Since the amount of data that can be transferred between micromanager and pycro-manager is currently limited to 100 MB/s, it's important that no more data is transferred to ensure smooth execution of the software.
For both movies, camera acquisition parameters in micromanager were set to:

    11-bit depth,
    chip-size cropped to the central 512x512 px.
    external trigger start (trigger comming at 45 Hz)
    exposure time set to 0.01 ms

Tested on:

    macOS Catalina using micromanager 2.0.0-gamma1-20201206
    Windows 10 using micromanager 2.0.0-gamma1-20201208


# required packages: 
# only execute first time to install all required packages
# has been tested with the indicated package versions
#!pip install pycromanager==0.10.9 napari==0.4.5 pyqt5==5.15.1 magicgui==0.2.5 yappi==1.3.2
# newest: magicgui==0.2.6, but there's an error message when connecting the buttons
"""

import time
import numpy as np
import queue
#import yappi # needed for benchmarking multithreaded code
import napari
from napari.qt import thread_worker
from magicgui import magicgui
from pycromanager import Acquisition, multi_d_acquisition_events
# open napari in an extra window, only needed for jupyter notebooks
#%gui qt



#########################################################################
#                          Define constants                             #
#########################################################################
# data acquired on microscope or simulated?
simulate = True
# z-stage controlled through micromanager, or externally?
z_stack_external = True
# clip image to central part. Speeds up display as data size is reduced
# is used as size for simulating data
clip =[512, 512]
# um / px, for correct scaling in napari
size_um = [0.16, 0.16]
# start in um, end in um, number of slices, active slice
z_range = [0, 50, 200, 0]
#z_range = [1100, 1150, 200, 0]
# rescale z dimension independently for display
z_scale = 1
# sleep time to keep software responsive
sleep_time = 0.01
# contrast limits for display
clim = [100, 300]
# number of color channels, active channel
channels = [1, 0] 
# color map for display
cmap = ['plasma', 'viridis']
# layer names for the channels
layer_names = ['GFP', 'RFP']

# initialize global variables
# flag to break while loops
acq_running = False
# empty queue for image data and z positions
img_queue = queue.Queue()
# xyz data stack
data = np.random.rand(z_range[2], clip[0], clip[1]) * clim[1]

# if z-stage is controlled through micromanager:
# need bridge to move stage at beginning of stack
# USE WITH CAUTION: only tested with micromanager demo config
if not(simulate) and not(z_stack_external):
    from pycromanager import _Bridge
    bridge = _Bridge()
    #get object representing micro-manager core
    core = bridge.get_core()
    print(core)
    core.set_position(z_range[0])
    
    
    
#########################################################################
#                   function to write data into queue                   #
#########################################################################    
def place_data(image):
    """ fnc to place image data into the queue.
        Keeps track of z-position in stacks and of active color channels.
        Inputs: np.array image: image data
        Global variables: image_queue to write image and z position
                            z_range to keep track of z position
                            channels to keep track of channels
    """
    global img_queue
    global z_range
    global channels
    img_queue.put([channels[1], z_range[3], np.ravel(image)], block = False)
    z_range[3] = (z_range[3]+1) % z_range[2]
    if z_range[3] == 0:
        channels[1] = (channels[1]+1) % channels[0]
    #print(z_range, channels)
    

    
#########################################################################
#                     functions creating dummy data                     #
#########################################################################      
def simulate_image(b, size = [128,128]):
    """ fnc to simulate an image of constant brightness
        and call fnc to place it into the queue.
        Inputs: int b: brightness
                np.array size: # of px in image in xy.
        """
    place_data(np.ones(size) * b)
    
    
def simulate_data(ii, z_range):
    """ fnc to create images with constant, but increasing brightness.
        Inputs: int ii: counter to increase brightness
                int z_range: number of slices in stack"""
    for zz in range(z_range[2]):
        brightness = (ii+1) * (zz+1) / ((z_range[2]+1)) * clim[1]
        simulate_image(brightness, clip)
        time.sleep(2*sleep_time)
        # need sleep time especially when simulated datasize is small or this will kill CPU
        
        
        
#########################################################################
#       Image processor functions grabbing data from micromanager       #
#########################################################################         
def grab_image(image, metadata):
    """ image_process_fnc to grab image from uManager, clip it to central part
        and call the fnc that will put it into the queue.
        Inputs: array image: image from micromanager
                metadata from micromanager
        """
    size = np.shape(image)
    image_clipped = image[(size[0]-clip[0])//2:(size[0]+clip[0])//2,
                      (size[1]-clip[1])//2:(size[1]+clip[1])//2]
    place_data(image_clipped)
   
    return image, metadata


def acquire_data(z_range):
    """ micro-manager data acquisition. Creates acquisition events for z-stack.
        This example: use custom events, not multi_d_acquisition because the 
        z-stage is not run from micro-manager but controlled via external DAQ."""
    with Acquisition(directory=None, name=None, 
                     show_display=True, 
                     image_process_fn = grab_image) as acq:
        events = []
        for index, z_um in enumerate(np.linspace(z_range[0], z_range[1], z_range[2])):
            evt = {"axes": {"z_ext": index}, "z_ext": z_um}
            events.append(evt)
        acq.acquire(events)
        
        
def acquire_multid(z_range):
    """ micro-manager data acquisition. Creates acquisition events for z-stack.
        This example: use multi_d_acquisition because the z-stage is run 
        from micro-manager.
        Unless hardware triggering is set up in micro-manager, this will be fairly slow:
        micro-manager does not sweep the z-stage, but acquires plane by plane. """
    with Acquisition(directory=None, name=None, 
                     show_display=False, 
                     image_process_fn = grab_image) as acq:
        events = multi_d_acquisition_events(z_start=z_range[0], z_end=z_range[1], 
                                            z_step=(z_range[1]-z_range[0])/(z_range[2]-1))
        acq.acquire(events)
        

        
#########################################################################
#                Function updating napari display                       #
#########################################################################  
def display_napari(pos_img):
    """ Unpacks z position and reshapes image from pos_img. Writes image into correct 
        slice of data, and updates napari display.
        Called by worker thread yielding elements from queue.
        Needs to be in code before worker thread connecting to it.
        Inputs: array pos_img: queue element containing z position and raveled image data.
        Global variables: np.array data: contains image stack
            img_queue: needed only to send task_done() signal.
    """
    global data
    global img_queue
    if pos_img is None:
        return
    # read image and z position
    image = np.reshape(pos_img[2:],(clip[0], clip[1]))
    z_pos = pos_img[1]
    color = pos_img[0]

    # write image into correct slice of data and update display
    data[z_pos] = np.squeeze(image)
    layer = viewer.layers[color]
    layer.data = data
    #print("updating ", z_pos, color)

    img_queue.task_done()
    
    
    
#########################################################################
#       Thread workers appending and reading data to / from queue       #
######################################################################### 
@thread_worker
def append_img(img_queue):
    """ Worker thread that adds images to a list.
        Calls either micro-manager data acquisition or functions for simulating data.
        Inputs: img_queue """
    # start microscope data acquisition
    if not simulate:
        if z_stack_external:
            while acq_running:
                acquire_data(z_range)
                time.sleep(sleep_time)
        else:
            while acq_running:
                acquire_multid(z_range)
                time.sleep(sleep_time)

    # run with simulated data
    else:
        ii = 0
        while acq_running:
            simulate_data(ii, z_range)
            ii = ii + 1
            #print("appending to queue", ii)
            time.sleep(sleep_time)
            
            
@thread_worker(connect={'yielded': display_napari})
def yield_img(img_queue):
    """ Worker thread that checks whether there are elements in the 
        queue, reads them out.
        Connected to display_napari function to update display """
    global acq_running
    
    while acq_running:
        time.sleep(sleep_time)
        # get elements from queue while there is more than one element
        # playing it safe: I'm always leaving one element in the queue
        while img_queue.qsize() > 1:
            #print("reading from queue ", img_queue.qsize())
            yield img_queue.get(block = False)

    # read out last remaining elements after end of acquisition
    while img_queue.qsize() > 0:
        yield img_queue.get(block = False)
    print("acquisition done")
    

#########################################################################
#        Functions to start / stop acquisition, buttons in napari       #
#########################################################################     
@magicgui(call_button="Start")
def start_acq():
    """ Called when Start button in pressed. Starts workers and resets global variables"""
    print("starting threads...")
    global acq_running
    global z_range
    if not(acq_running):
        z_range[3] = 0
        acq_running = True
        # comment in when benchmarking
        #yappi.start()
        worker1 = append_img(img_queue)
        worker2 = yield_img(img_queue)
        worker1.start()
        #worker2.start() # doesn't need to be started bc yield is connected
    else:
        print("acquisition already running!")
    
    
@magicgui(call_button = "Stop")
def stop_acq():
    print("stopping threads")
    # set global acq_running to False to stop other workers
    global acq_running
    global core
    acq_running = False
    if not(simulate) and not(z_stack_external):
        print('z stage stopping: ', core.get_position())
        core.stop("Z") # this doesnt work, just continues moving. eventually micromanager memory overflows
        print('z stage stopped: ', core.get_position())        
        core.set_position(z_range[0]) # this also doesn't work
        core.wait_for_device("Z")
        #time.sleep(5)
        print('z stage zeroed: ', core.get_position())
    
    
    
#########################################################################
#      Main function starting napari window and initializing views      #
#########################################################################         

if __name__ == "__main__":
    with napari.gui_qt():
        # check if viewer is already open
        # if yes: close and reopen
        try:
            if viewer:
                viewer.close()
        except:
            print("viewer already closed or never opened")
        viewer = napari.Viewer(ndisplay=2)

        # initialize napari viewer with stack view and random data, reslice view
        scale = [(z_range[1]-z_range[0])/z_range[2]*z_scale, size_um[1], size_um[0]]
        layers = [viewer.add_image(data, 
                                name = layer_names[c],
                                colormap = cmap[c],
                                interpolation = 'nearest',
                                blending = 'additive',
                                rendering = 'attenuated_mip',
                                scale = scale,
                                contrast_limits = clim) 
                 for c in range(channels[0])]
        viewer.dims._roll()

        # set sliders to the middle of the stack for all three dimensions.
        # doesn't work anymore after fixing scaling
        # would have to be done for both layers
        #for dd, dim in enumerate(layers[0].data.shape):
        #    viewer.dims.set_point(dd, dim*scale[2-dd]//2)

        # define start stop buttons and add to napari gui
        # these will break when upgrading to magicgui v0.2.0
        gui_start = start_acq.Gui()
        gui_stop = stop_acq.Gui()
        viewer.window.add_dock_widget(gui_start)
        viewer.window.add_dock_widget(gui_stop)
        bridge.close()
