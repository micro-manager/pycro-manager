****************************
Applications
****************************


Have an application you'd like to contribute to this page? Please `reach out <https://github.com/micro-manager/pycro-manager/issues/new>`_!


.. toctree::
	:maxdepth: 1
	:caption: Contents:

	intermittent_Z_T.ipynb
	TZYX_fast_sequencing_z_indexing.ipynb
	convert_MM_MDA_data_into_zarr.ipynb
	pycro_manager_imjoy_tutorial.ipynb
	Denoising acquired images using deep learning.ipynb
	pycro_manager_tie_demo.ipynb
	guiding_acq_with_neural_network_attention.ipynb
	Auto_CycIF.ipynb


:doc:`intermittent_Z_T`
	This notebook shows how to repeatedly acquire a short time series and then a z stack at a set with a set delay in between.

:doc:`TZYX_fast_sequencing_z_indexing`
	This notebook acquires a fast TZYX data series. The camera is run at reduced ROI to achieve higher framerate (here 200 frames per second). Movement of the z stage is "sequenced" to speed up acquisition. The z stage advances to the next position in the sequence when a trigger from the camera is received. This eliminates delays due to software communication.

:doc:`convert_MM_MDA_data_into_zarr`
	This notebook explains how to use Pycromanger to readout the data saved by Micro-manager's multi-dimensional acquisition and convert it into zarr format. This is useful when the data is large (more than hundreds of GBs). Currently there is no python reader that can directly readout the large multi-dimensional data saved by Micromanger. The Pycro-Manager Java Python Bridge makes this possible.

:doc:`pycro_manager_imjoy_tutorial`
	This tutorial notebook shows how you can combine Pycro-Manager with `ImJoy <https://imjoy.io/>`_ which is a web framework for building rich and powerful interactive analysis tools. 
	Step by step, it shows how you can use ImJoy plugins for acquiring and visualzing images using a dedicated ImJoy plugin for Pycro-Manager in the notebook with snap/live buttons, exposure/binning controls and a full-featured device property browser. The built plugin can be hosted on Github, and use independently outside the Jupyter notebook interface.

:doc:`Denoising acquired images using deep learning`
	 This tutorial demonstrates how to train a deep learning model for image denoising using data aquired by Pycro-Manager. This training is performed on Google Colab, which provides free usage of GPUs in the cloud, so no specialized hardware is required to implement it. The trained model will then be used to denoise images in real time using a Pycro-Manager image processor. 

:doc:`pycro_manager_tie_demo`
	This example shows how to compute 2D quantitative phase images from collected focal stacks, without the need for specialized optics, using computational imaging. Specifically, we will solve and inverse problem based on the `Transport of Intensity Equation (TIE) <https://en.wikipedia.org/wiki/Transport-of-intensity_equation>`_. The inverse problem is implemented in an image processor, to enable on-the-fly quantitative phase imaging during acquisition.

:doc:`guiding_acq_with_neural_network_attention`
	This tutorial shows how to use Pycro-manager to perform analysis driven targeted multimodal/multiscale acquisition for automated collagen fiber-based biomarker identification. We will acquire brightfield images of a H&E stained cancer histology slide at 4x magnification, identify pathology relevant ROIs using a deep learning model based on the 4x image, and zoom into these ROIs to perform the collagen fiber-specific method of second-harmonic generation (SHG) laser scanning at 20x magnification. This allows for disease-relevant, collagen-specific features to be collected automatically and correlated with the gold standard H&E pathology method. We use Pycro-manager to read/write hardware properties (e.g. camera exposure, lamp intensity, turret position, stage position, etc.), change Micro-Manager hardware property configuration groups, acquire images and access the image data as NumPy array, and perform Z-stack acquisition via multi-dimension acquisition events.

:doc:`Auto_CycIF`
	This notebook shows an implementation of the `CycIF <https://www.cycif.org/>`_ Multiplex immunostaining method on several slides in parallel. It utilizes Micro-Magellan as a user interface to define the bounds of each tissue section, calculates the center of the section, and uses this coordinate to drive the stage underneath the robotic pipettor for staining cycles. It also executes autofocus routines at sub-sampled tiles to provide speed increases. It goes through typical 4 color images and sets an executes a simple auto-expose routine and calculates new exposure times. Finally, it takes the saved data and repackages it into a format that the alignment and stitching software, Ashlar, can accept. 

