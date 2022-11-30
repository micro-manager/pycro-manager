import os
import shutil
import subprocess
import pytest
import wget
import requests
import re
import glob
from pycromanager import start_headless
from pycromanager.acq_util import cleanup


def find_jar(pathname, jar_name):
    p = re.compile(jar_name + r"-\d+.\d+\.\d+.jar")

    for path in os.listdir(pathname):
        match = p.match(path)
        if match:
            return path


@pytest.fixture()
def download_mm_nightly(printer):
    # get latest mm nightly build
    mm_windows_downloads = "https://download.micro-manager.org/nightly/2.0/Windows/"
    webpage = requests.get(mm_windows_downloads)

    m = re.search(r'class="rowDefault" href="([^"]+)', webpage.text)
    url = "https://download.micro-manager.org" + m.group(1)

    # download
    printer(f"Downloading Micro-manager nightly build: {url.split('/')[-1]}")
    mm_installer = os.path.join(os.getcwd(), 'mm_nightly_build.exe')
    if not os.path.exists(mm_installer):
        wget.download(url, out=mm_installer)

    yield mm_installer

    # cleanup
    os.remove(mm_installer)


@pytest.fixture()
def install_mm(printer, download_mm_nightly):
    mm_installer = download_mm_nightly
    mm_install_dir = os.path.join(os.path.expanduser('~'), "Micro-Manager-nightly")
    mm_install_log_path = os.path.join(os.path.dirname(mm_installer), "mm_install.log")

    # check that java dependencies are present
    if os.path.isdir('java'):
        java_path = os.path.abspath('java')
    # in case cwd is '/pycromanager/test'
    elif os.path.isdir('../../java'):
        java_path = os.path.abspath('../../java')
    else:
        raise RuntimeError('Could not find pycro-manager/java path')

    if not os.path.isdir(os.path.join(java_path, 'target')) \
            or not os.path.isdir(os.path.join(java_path, 'target/dependency')):
        raise FileNotFoundError('Please build Java dependencies before running pytest.')

    PycroManagerJava_path = find_jar(os.path.join(java_path, 'target'), 'PycroManagerJava')
    AcqEngJ_path = find_jar(os.path.join(java_path, 'target/dependency'), 'AcqEngJ')
    NDTiffStorage_path = find_jar(os.path.join(java_path, 'target/dependency'), 'NDTiffStorage')
    NDViewer_path = find_jar(os.path.join(java_path, 'target/dependency'), 'NDViewer')

    if not PycroManagerJava_path \
            or not AcqEngJ_path \
            or not NDTiffStorage_path \
            or not NDViewer_path:
        raise FileNotFoundError('Please build Java dependencies before running pytest.')

    # remove install dir if it exists, better to remove it at cleanup instead
    if os.path.exists(mm_install_dir):
        printer(f'Removing previous Micro-manager installation at: {mm_install_dir}')
        shutil.rmtree(mm_install_dir)
    os.mkdir(mm_install_dir)

    printer(f'Installing Micro-manager nightly build at: {mm_install_dir}')
    cmd = f"{mm_installer} /SP /VERYSILENT /SUPRESSMSGBOXES /CURRENTUSER /DIR={mm_install_dir} /LOG={mm_install_log_path}"

    subprocess.run(cmd, shell=True)

    yield mm_install_dir

    # cleanup
    os.remove(mm_install_log_path)
    # fails, because MM is still running, I think
    # shutil.rmtree(mm_install_dir)


@pytest.fixture()
def launch_mm_headless(printer, install_mm):
    mm_install_dir = install_mm
    config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')

    printer('Launching Micro-manager in headless mode.')
    start_headless(mm_install_dir, config_file)

    # yield None
    #
    # cleanup()
