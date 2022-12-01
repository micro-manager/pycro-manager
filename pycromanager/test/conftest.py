import os
import shutil
import subprocess
import pytest
import wget
import requests
import re
from pycromanager import start_headless
from pycromanager.acq_util import cleanup


def find_jar(pathname, jar_name):
    p = re.compile(jar_name + r"-\d+.\d+\.\d+.jar")

    for path in os.listdir(pathname):
        match = p.match(path)
        if match:
            return path


def replace_jars(new_file_path, old_file_path, jar_names: list):
    for jar_name in jar_names:
        new_jar = find_jar(new_file_path, jar_name)
        old_jar = find_jar(old_file_path, jar_name)
        if new_jar is None:
            FileNotFoundError(f'{jar_name} not found in {new_file_path}')

        print(f'Replacing {old_jar} in {old_file_path} with {new_jar}.')
        os.remove(os.path.join(old_file_path, old_jar))
        shutil.copy2(os.path.join(new_file_path, new_jar), os.path.join(old_file_path, old_jar))


@pytest.fixture(scope="session")
def download_mm_nightly():
    # get latest mm nightly build
    mm_windows_downloads = "https://download.micro-manager.org/nightly/2.0/Windows/"
    webpage = requests.get(mm_windows_downloads)

    m = re.search(r'class="rowDefault" href="([^"]+)', webpage.text)
    url = "https://download.micro-manager.org" + m.group(1)

    # download
    print(f"\nDownloading Micro-manager nightly build: {url.split('/')[-1]}")
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

    # remove install dir if it exists, better to remove it at cleanup instead
    if os.path.exists(mm_install_dir):
        print(f'Removing previous Micro-manager installation at: {mm_install_dir}')
        shutil.rmtree(mm_install_dir)
    os.mkdir(mm_install_dir)

    print(f'Installing Micro-manager nightly build at: {mm_install_dir}')
    cmd = f"{mm_installer} /SP /VERYSILENT /SUPRESSMSGBOXES /CURRENTUSER /DIR={mm_install_dir} /LOG={mm_install_log_path}"
    subprocess.run(cmd, shell=True)

    # update pycromanager jar files with those newly compiled
    replace_jars(os.path.join(java_path, 'target'), os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'),
                 ['PycroManagerJava'])
    replace_jars(os.path.join(java_path, 'target/dependency'), os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'),
                 ['AcqEngJ', 'NDTiffStorage', 'NDViewer'])

    yield mm_install_dir

    # cleanup
    os.remove(mm_install_log_path)
    # fails, because MM is still running, I think
    # shutil.rmtree(mm_install_dir)


@pytest.fixture(scope="session")
def setup_data_folder():
    data_folder_path = os.path.join(os.getcwd(), 'temp_data')
    if not os.path.isdir(data_folder_path):
        os.mkdir(data_folder_path)

    yield data_folder_path

    shutil.rmtree(data_folder_path)


@pytest.fixture(scope="session")
def launch_mm_headless(install_mm):
    mm_install_dir = install_mm
    config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')

    print('Launching Micro-manager in headless mode.')
    start_headless(mm_install_dir, config_file)

    # yield None
    #
    # cleanup()
