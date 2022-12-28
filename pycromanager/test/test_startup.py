import os
from pycromanager import Core


def test_connect_to_core(launch_mm_headless):
    mmc = Core()

    assert mmc._java_class == 'mmcorej.CMMCore'
