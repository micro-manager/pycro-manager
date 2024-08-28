****************************
Application Tutorials
****************************

.. toctree::
    :maxdepth: 2
    :hidden:

    application_notebooks/TZYX_fast_sequencing_z_indexing.ipynb
    application_notebooks/pycro_manager_imjoy_tutorial.ipynb
    application_notebooks/Denoising acquired images using deep learning.ipynb
    application_notebooks/Single_shot_autofocus_pycromanager.ipynb
    application_notebooks/guiding_acq_with_neural_network_attention.ipynb
    application_notebooks/Learned_adaptive_multiphoton_illumination.ipynb


:doc:`application_notebooks/TZYX_fast_sequencing_z_indexing`
	This notebook acquires a fast TZYX data series. The camera is run at reduced ROI to achieve higher framerate (here 200 frames per second). Movement of the z stage is "sequenced" to speed up acquisition. The z stage advances to the next position in the sequence when a trigger from the camera is received. This eliminates delays due to software communication.

:doc:`application_notebooks/pycro_manager_imjoy_tutorial`
	This tutorial notebook shows how you can combine pycro-manager with `ImJoy <https://imjoy.io/>`_ which is a web framework for building rich and powerful interactive analysis tools.
	Step by step, it shows how you can use ImJoy plugins for acquiring and visualzing images using a dedicated ImJoy plugin for Pycro-Manager in the notebook with snap/live buttons, exposure/binning controls and a full-featured device property browser. The built plugin can be hosted on Github, and use independently outside the Jupyter notebook interface.

:doc:`application_notebooks/Denoising acquired images using deep learning`
    This tutorial demonstrates how to train a deep learning model for image denoising using data acquired by Pycro-Manager. This training is performed on Google Colab, which provides free usage of GPUs in the cloud, so no specialized hardware is required to implement it. The trained model will then be used to denoise images in real time using a Pycro-Manager image processor.

:doc:`application_notebooks/Single_shot_autofocus_pycromanager`
	This notebook shows how to use Pycro-Manager/Micro-Magellan to implement machine learning-powered, image-based autofocus, as detailed in `this paper <https://doi.org/10.1364/OPTICA.6.000794>`_. It shows how to set up and use Micro-Magellan to collect training data, and how to use an acquisition hook to apply focus corrections during an experiment.

:doc:`application_notebooks/guiding_acq_with_neural_network_attention`
	This tutorial shows how to use pycro-manager to perform analysis driven targeted multimodal/multiscale acquisition for automated collagen fiber-based biomarker identification. We will acquire brightfield images of a H&E stained cancer histology slide at 4x magnification, identify pathology relevant ROIs using a deep learning model based on the 4x image, and zoom into these ROIs to perform the collagen fiber-specific method of second-harmonic generation (SHG) laser scanning at 20x magnification. This allows for disease-relevant, collagen-specific features to be collected automatically and correlated with the gold standard H&E pathology method. We use Pycro-manager to read/write hardware properties (e.g. camera exposure, lamp intensity, turret position, stage position, etc.), change Micro-Manager hardware property configuration groups, acquire images and access the image data as NumPy array, and perform Z-stack acquisition via multi-dimension acquisition events.

:doc:`application_notebooks/Learned_adaptive_multiphoton_illumination`
	This tutorial demonstrates how to implement `Learned Adaptive Multiphoton Illumination microscopy <https://doi.org/10.1038/s41467-021-22246-5>`_ using Pycro-Manager/Micro-Magellan. This technique enables automatic sample-dependent adjustment of excitation laser power in real time while imaging a sample on a 2-photon microscope in order to compensate for attenuation of fluorescence when imaging deep into intact tissue.

