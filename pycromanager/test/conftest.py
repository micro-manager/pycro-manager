import os
import shutil
import subprocess
import pytest
import wget
import requests
import re
from pycromanager import start_headless
from pycromanager.acq_util import cleanup


@pytest.fixture(scope="session")
def download_mm_nightly():
    # get latest mm nightly build
    mm_windows_downloads = "https://download.micro-manager.org/nightly/2.0/Windows/"
    webpage = requests.get(mm_windows_downloads)

    m = re.search(r'class="rowDefault" href="([^"]+)', webpage.text)
    url = "https://download.micro-manager.org" + m.group(1)

    # download
    mm_installer = os.path.join(os.getcwd(), 'mm_nightly_build.exe')
    if not os.path.exists(mm_installer):
        wget.download(url, out=mm_installer)

    yield mm_installer

    # cleanup
    os.remove(mm_installer)


@pytest.fixture(scope="session")
def install_mm(download_mm_nightly):
    mm_installer = download_mm_nightly
    mm_install_dir = os.path.join(os.path.expanduser('~'), "Micro-Manager-nightly")
    mm_install_log_path = os.path.join(os.path.dirname(mm_installer), "mm_install.log")

    # remove install dir if it exists, better to remove it at cleanup instead
    if os.path.exists(mm_install_dir):
        shutil.rmtree(mm_install_dir)
    os.mkdir(mm_install_dir)

    cmd = f"{mm_installer} /SP /VERYSILENT /SUPRESSMSGBOXES /CURRENTUSER /DIR={mm_install_dir} /LOG={mm_install_log_path}"

    subprocess.run(cmd, shell=True)

    yield mm_install_dir

    # cleanup
    os.remove(mm_install_log_path)
    # fails, because MM is still running, I think
    # shutil.rmtree(mm_install_dir)


@pytest.fixture(scope="session")
def launch_mm_headless(install_mm):
    mm_install_dir = install_mm
    config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')

    start_headless(mm_install_dir, config_file)

    # yield None
    #
    # cleanup()
