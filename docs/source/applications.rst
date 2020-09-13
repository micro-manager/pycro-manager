****************************
Applications
****************************


Have an application you'd like to figure out how to enable or add to this page? Please `reach out <https://github.com/micro-manager/pycro-manager/issues/new>`_!


##########################################################################################################
`Targeted multi-contrast microscopy using attention-based multi-instance learning for tissue sections`_
##########################################################################################################

This tutorial shows how to use Pycro-manager to perform analysis driven targeted multimodal/multiscale acquisition for automated collagen fiber-based biomarker identification. We will acquire brightfield images of a H&E stained cancer histology slide at 4x magnification, identify pathology relevant ROIs using a deep learning model based on the 4x image, and zoom into these ROIs to perform the collagen fiber-specific method of second-harmonic generation (SHG) laser scanning at 20x magnification. This allows for disease-relevant, collagen-specific features to be collected automatically and correlated with the gold standard H&E pathology method. We use Pycro-manager to read/write hardware properties (e.g. camera exposure, lamp intensity, turret position, stage position, etc.), change Micro-Manager hardware property configuration groups, acquire images and access the image data as NumPy array, and perform Z-stack acquisition via multi-dimension acquisition events.

