import os
import sys
import shutil
import subprocess
import pytest
import wget
import requests
import re
import time
import glob

import pycromanager
from pycromanager import start_headless
from pycromanager.headless import stop_headless
import socket

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_jar(pathname, jar_name):
    p = re.compile(jar_name + r"-(\d+).(\d+).(\d+).jar")

    path = None
    version = (0, 0, 0)
    for _path in os.listdir(pathname):
        match = p.match(_path)
        if match:
            # get file with the latest version
            _version = tuple([int(i) for i in match.groups()])
            if _version[0] > version[0] or _version[1] > version[1] or _version[2] > version[2]:
                version = _version
                path = _path

    return path, version


def replace_jars(new_file_path, old_file_path, jar_names: list):
    for jar_name in jar_names:
        new_jar_name, new_jar_version = find_jar(new_file_path, jar_name)
        old_jar_name, old_jar_version = find_jar(old_file_path, jar_name)

        if new_jar_name is not None:
            # Only replace jar file if newly compiled file version is larger
            if new_jar_version[0] > old_jar_version[0] or \
                    new_jar_version[1] > old_jar_version[1] or \
                    new_jar_version[2] > old_jar_version[2]:

                print(f'Replacing {old_jar_name} in {old_file_path} with {new_jar_name}.')
                os.remove(os.path.join(old_file_path, old_jar_name))
                shutil.copy2(os.path.join(new_file_path, new_jar_name), os.path.join(old_file_path, old_jar_name))


@pytest.fixture(scope="session")
def download_mm_nightly():
    if is_port_in_use(4827):
        yield
    else:
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
        if os.path.isfile(mm_installer):
            os.remove(mm_installer)


@pytest.fixture(scope="session")
def install_mm(download_mm_nightly):
    mm_installed = False
    mm_running = False
    mm_install_dir = os.path.join(os.path.expanduser('~'), "Micro-Manager-nightly")


    # check if there is currently a Micro-manager instance running (used for local testing)
    if is_port_in_use(4827):
        mm_running = True
        print('Using Micro-manager running on port 4827 for testing')
        yield
    else:
        if os.path.isdir(mm_install_dir) and os.listdir(mm_install_dir):
            # Check if Micro-manager installation is present in mm_install_dir.
            # If so, the latest Micro-manager nightly build will not be installed.
            print(f'Existing Micro-manager installation found at {mm_install_dir}')
        else:
            # Install Micro-manager nightly build. Currently only supported on Windows platforms
            # To run tests on other platform, please place a working Micro-manager installation in "~/Micro-Manager-nightly"
            mm_installed = True

            if sys.platform.startswith('win'):
                mm_installer = download_mm_nightly
                mm_install_log_path = os.path.join(os.path.dirname(mm_installer), "mm_install.log")
            else:
                raise RuntimeError(
                    '''Micro-manager nightly build installation is currently only supported on Windows platforms. 
                To run tests on other platform, please place a working Micro-manager installation in 
                "~/Micro-Manager-nightly"'''
                )

            # mkdir if not exists
            if not os.path.isdir(mm_install_dir):
                os.mkdir(mm_install_dir)

            print(f'Installing Micro-manager nightly build at: {mm_install_dir}')
            cmd = f"{mm_installer} /SP /VERYSILENT /SUPRESSMSGBOXES /CURRENTUSER /DIR={mm_install_dir} /LOG={mm_install_log_path}"
            subprocess.run(cmd, shell=True)

            # find pycro-manager/java path
            if os.path.isdir('java'):
                java_path = os.path.abspath('java')
            # in case cwd is '/pycromanager/test'
            elif os.path.isdir('../../java'):
                java_path = os.path.abspath('../../java')
            else:
                raise RuntimeError('Could not find pycro-manager/java path')


            # Delete the pycromanagerjava.jar file that is packaged with the nightly build
            # use a wildcard to match the version number
            pycromanager_jar_path = os.path.join(mm_install_dir, 'plugins', 'Micro-Manager', 'PycromanagerJava-[0-9]*.[0-9]*.[0-9]*.jar')
            for file_path in glob.glob(pycromanager_jar_path):
                os.remove(file_path)
                print(f'Removed {file_path}')

            # Copy the pycromanagerjava.jar file that was compiled by the github action
            # into the nightly build so that it will test with the latest code
            compiled_jar_path = os.path.join(java_path, 'target', 'PycromanagerJava-[0-9]*.[0-9]*.[0-9].jar')            # Destination path where the jar file should be copied to
            destination_path = os.path.join(mm_install_dir, 'plugins', 'Micro-Manager', 'PycromanagerJava.jar')
            # Find the actual file that matches the pattern and copy it to the destination
            for file_path in glob.glob(compiled_jar_path):
                shutil.copy2(file_path, destination_path)
                print(f'Copied {file_path} to {destination_path}')

            # Update pycromanager dependency jar files packaged with the Micro-manager nightly build
            # Files are updated only if they are larger version
            # Copy dependency jar files if present in target/dependency
            if os.path.isdir(os.path.join(java_path, 'target/dependency')):
                replace_jars(os.path.join(java_path, 'target/dependency'), os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'),
                        ['AcqEngJ', 'NDTiffStorage', 'NDViewer'])
            # Copy dependency jar files if present in ../../REPO_NAME/target
            for repo_name in ['AcqEngJ', 'NDTiffStorage', 'NDViewer']:
                if os.path.isdir(os.path.join(java_path, f'../../{repo_name}/target')):
                    replace_jars(os.path.join(java_path, f'../../{repo_name}/target'),
                                    os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'), [repo_name])

        yield mm_install_dir

    # cleanup only if Micro-manager was installed in this session
    if not mm_running and mm_installed:
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
    if mm_install_dir is None:
        yield # local manual testing where MM has been launched from source
    else:
        config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
        print('Launching Micro-manager in headless mode.')

        # MM doesn't ship with Java on Mac so allow it to be defined here
        java_loc = None
        if "JAVA" in os.environ:
            java_loc = os.environ["JAVA"]

        start_headless(mm_install_dir, config_file, java_loc=java_loc, debug=True)

        yield None

        stop_headless(debug=True)
