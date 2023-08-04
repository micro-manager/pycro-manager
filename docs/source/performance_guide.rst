.. _performance_guide:

**************************
Performance Guide
**************************

With a proper hardware and software setup, pycromanager is capable of handling extremely large data volumes and rates (such as those seen in light sheet microscopy). The writer for the default format of pycromanager (`NDTiff <https://github.com/micro-manager/NDTiffStorage>`_), with multiple NVMe drives in a RAID configuration, has been clocked at sustaining multiple GB/s write speeds for hours at a time.

However, one performance limitation is the ~100 MB/s upper limit on data transfer over the Java-Python translation layer. The current implementation of :ref:`img_processors` are bound by this limit, so if extremely fast data rates are needed, they should be avoided. One alternative is to use :ref:`image_saved_callbacks`, which do not send data between Java and Python directly. Instead, after each image is written to disk, a small message is sent from Java to Python describing the location of the new data on disk. This can data can then be read data natively in Python, without incurring the translation layer speed limits.
