import os
import sys
import shutil
import warnings

import pytest
import re
import glob

from pycromanager import start_headless, stop_headless
import socket
from mmpycorex import download_and_install_mm, find_existing_mm_install

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

        print('Old version:', old_jar_name, old_jar_version)
        print('New version:', new_jar_name, new_jar_version)
        if new_jar_name is not None:
            # Only replace jar file if newly compiled file version is larger
            if new_jar_version[0] > old_jar_version[0] or \
                    new_jar_version[1] > old_jar_version[1] or \
                    new_jar_version[2] > old_jar_version[2]:

                print(f'Replacing {old_jar_name} in {old_file_path} with {new_jar_name}.')
                os.remove(os.path.join(old_file_path, old_jar_name))
                shutil.copy2(os.path.join(new_file_path, new_jar_name), os.path.join(old_file_path, old_jar_name))


@pytest.fixture(scope="session")
def install_mm():
    if is_port_in_use(4827):
        print('Using Micro-manager running on port 4827 for testing')
        yield
    elif find_existing_mm_install():
        print('Micro-Manager is already installed, skipping installation')
        yield find_existing_mm_install()
    else:
        # Download an install latest nightly build
        mm_install_dir = download_and_install_mm(destination='auto')

        #### Replace with newer versions of Java libraries ####
        # find pycro-manager/java path
        if os.path.isdir('java'):
            java_path = os.path.abspath('java')
        # in case cwd is '/pycromanager/test'
        elif os.path.isdir('../../java'):
            java_path = os.path.abspath('../../java')
        else:
            raise RuntimeError('Could not find pycro-manager/java path')

        # Delete the pycromanagerjava.jar file that is packaged with the nightly build
        try:
            pycromanager_jar_path = os.path.join(mm_install_dir, 'plugins', 'Micro-Manager', 'PycromanagerJava-*.jar')
            for file_path in glob.glob(pycromanager_jar_path):
                os.remove(file_path)
                print(f'Removed {file_path}')

            # Copy the pycromanagerjava.jar file that was compiled by the github action
            # into the nightly build so that it will test with the latest code
            compiled_jar_path = os.path.join(java_path, 'target', 'PycromanagerJava-*.jar')
            destination_path = os.path.join(mm_install_dir, 'plugins', 'Micro-Manager', 'PycromanagerJava.jar')

            # Find the actual file that matches the pattern and copy it to the destination
            matched_files = [file for file in glob.glob(compiled_jar_path)
                             if not any(exclude in file for exclude in ['-javadoc', '-sources', '.asc', '.pom'])]
            if matched_files:
                file_path = matched_files[0]
                shutil.copy2(file_path, destination_path)
                print(f'Copied {file_path} to {destination_path}')
            else:
                print(f'No matching JAR file found at {compiled_jar_path}')
                raise FileNotFoundError(f'No matching JAR file found at {compiled_jar_path}')

            # Update pycromanager dependency jar files packaged with the Micro-manager nightly build
            # Files are updated only if they are larger version
            # Copy dependency jar files if present in target/dependency
            if os.path.isdir(os.path.join(java_path, 'target/dependency')):
                # print jars present here
                print('JAR files present in target/dependency:')
                for f in os.listdir(os.path.join(java_path, 'target/dependency')):
                    print(f)
                replace_jars(os.path.join(java_path, 'target/dependency'), os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'),
                        ['AcqEngJ', 'NDTiffStorage', 'NDViewer', 'PyJavaZ'])


            # Not needed because deps of deps are already included in the JARs?
            # Copy dependency jar files if present in ../../REPO_NAME/target
            # for repo_name in ['AcqEngJ', 'NDTiffStorage', 'NDViewer', 'PyJavaZ']:
            #     print(f'JAR files present in {repo_name}/target:')
            #     for f in os.listdir(os.path.join(java_path, f'../../{repo_name}/target')):
            #         print(f)
            #     if os.path.isdir(os.path.join(java_path, f'../../{repo_name}/target')):
            #         replace_jars(os.path.join(java_path, f'../../{repo_name}/target'),
            #                         os.path.join(mm_install_dir, 'plugins', 'Micro-Manager'), [repo_name])

        except Exception as e:
            warnings.warn(f'Failed to replace JAR files: {e}')
            # let this continue so python tests can still run

        yield mm_install_dir



@pytest.fixture(scope="session",  params=['save_to_disk', 'RAM'])
def setup_data_folder(request):
    if request.param != 'save_to_disk':
        yield None
    else:
        data_folder_path = os.path.join(os.getcwd(), 'temp_data')
        if not os.path.isdir(data_folder_path):
            os.mkdir(data_folder_path)

        yield data_folder_path

        shutil.rmtree(data_folder_path)


@pytest.fixture(scope="session", params=['python_backend', 'java_backend'])
def launch_mm_headless(request, install_mm):
    python_backend = request.param == 'python_backend'
    mm_install_dir = install_mm
    if not python_backend:
        if mm_install_dir is None:
            yield # local manual testing where MM has been launched from source
        else:
            config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
            print('Launching Micro-manager in headless mode.')

            # MM doesn't ship with Java on Mac so allow it to be defined here if using mac os
            java_loc = None
            if "JAVA" in os.environ and sys.platform == "darwin":
                java_loc = os.environ["JAVA"]

            start_headless(mm_install_dir, config_file, java_loc=java_loc,
                           buffer_size_mb=2048, max_memory_mb=2048, # set these low for github actions
                           debug=True)

            yield

            stop_headless(debug=True)
    else: # python backend
        config_file = os.path.join(mm_install_dir, 'MMConfig_demo.cfg')
        start_headless(mm_install_dir, config_file,
                       buffer_size_mb=2048, max_memory_mb=2048,  # set these low for github actions
                       python_backend=True,
                       debug=True)
        yield
        stop_headless(debug=True)
