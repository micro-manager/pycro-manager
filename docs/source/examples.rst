Maybe more examples
===================

- snap in image within the acquisition cycle (eg autofocus)


Search for device, connect and read characteristic
**************************************************
.. code-block:: python

    """This example demonstrates a simple BLE client that scans for devices,
    connects to a device (GATT server) of choice and continuously reads a characteristic on that device.

    The GATT Server in this example runs on an ESP32 with Arduino. For the
    exact script used for this example see `here <https://github.com/nkolban/ESP32_BLE_Arduino/blob/6bad7b42a96f0aa493323ef4821a8efb0e8815f2/examples/BLE_notify/BLE_notify.ino/>`_
    """

    from bluepy.btle import *
    from simpleble import SimpleBleClient, SimpleBleDevice

    # The UUID of the characteristic we want to read and the name of the device # we want to read it from
    Characteristic_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
    Device_Name = "MyESP32"