"""
Utility functions for installing micro-manager
"""
import sys
import os
import re
import requests
import wget
import subprocess
import shutil

MM_DOWNLOAD_URL_BASE = 'https://download.micro-manager.org'

MM_DOWNLOAD_URL_MAC = MM_DOWNLOAD_URL_BASE + '/nightly/2.0/Mac'
MM_DOWNLOAD_URL_WINDOWS = MM_DOWNLOAD_URL_BASE + '/nightly/2.0/Windows'

def _get_download_url(ci_build=False):
    """
    Get the download URL for the latest nightly build of Micro-Manager

    Returns
    -------
    str
        The URL to the latest nightly build
    """
    platform = _get_platform()
    if platform == 'Windows':
        url = MM_DOWNLOAD_URL_WINDOWS
    elif platform == 'Mac':
        url = MM_DOWNLOAD_URL_MAC
    else:
        raise ValueError(f"Unsupported OS: {platform}")
    if ci_build:
        url = url.replace('nightly', 'ci')
    return url

def _get_platform():
    """
    Get the platform of the system

    Returns
    -------
    str
        "Windows" or "Mac"
    """
    if sys.platform.startswith('win'):
        return 'Windows'
    elif sys.platform.startswith('darwin'):
        return 'Mac'
    else:
        raise ValueError(f"Unsupported OS: {sys.platform}")

def _find_versions(ci_build=False):
    """
    Find all available versions of Micro-Manager  builds
    """
    # Get the webpage
    webpage = requests.get(_get_download_url(ci_build))
    return re.findall(r'class="rowDefault" href="([^"]+)', webpage.text)

def find_existing_mm_install():
    """
    Check if Micro-Manager is installed in the default auto-download paths

    Returns
    -------
    str
        The path to the installed Micro-Manager directory, or None if not found
    """
    platform = _get_platform()
    if platform == 'Windows':
        if os.path.isdir(r'C:\Program Files\Micro-Manager'):
            return r'C:\Program Files\Micro-Manager'
    elif platform == 'Mac':
        if os.path.isdir(str(os.path.expanduser('~')) + '/Micro-Manager'):
            return str(os.path.expanduser('~')) + '/Micro-Manager'
    else:
        raise ValueError(f"Unsupported OS: {platform}")

def download_and_install(destination='auto', mm_install_log_path=None, ci_build=False):
    """
    Download and install the latest nightly build of Micro-Manager

    Parameters
    ----------
    destination : str
        The directory to install Micro-Manager to. If 'auto', it will install to the user's home directory.
    mm_install_log_path : str
        Path to save the installation log to
    ci_build : bool
        If True, download the latest CI build instead of nightly build

    Returns
    -------
    str
        The path to the installed Micro-Manager directory
    """
    windows = _get_platform() == 'Windows'
    platform = 'Windows' if windows else 'Mac'
    installer = 'mm_installer.exe' if windows else 'mm_installer.dmg'
    latest_version = _get_download_url(ci_build) + '/' + _find_versions(ci_build)[0].split('/')[-1]
    # make a progress bar that updates every 0.5 seconds
    def bar(curr, total, width):
        if not hasattr(bar, 'last_update'):
            bar.last_update = 0
        if curr / total*100 - bar.last_update > 0.5:
            print(f"\rDownloading installer: {curr / total*100:.2f}%", end='')
            bar.last_update = curr / total*100
    print('Downloading: ', latest_version)
    wget.download(latest_version, out=installer, bar=bar)

    if windows:
        if destination == 'auto':
            destination = r'C:\Program Files\Micro-Manager'
        cmd = f"{installer} /SP /VERYSILENT /SUPRESSMSGBOXES /CURRENTUSER /DIR=\"{destination}\""

        if mm_install_log_path:
            cmd += f" /LOG={mm_install_log_path}"
        subprocess.run(cmd, shell=True)

        return destination
    else:
        if destination == 'auto':
            destination = str(os.path.expanduser('~')) + '/Micro-Manager'
        try:
            # unmount if already mounted
            subprocess.run(['hdiutil', 'detach', '/Volumes/Micro-Manager'])
        except:
            pass
        process = subprocess.run(['hdiutil', 'attach', '-nobrowse', str(installer)])
        latest_build = [name for name in os.listdir('/Volumes/Micro-Manager') if 'Micro-Manager' in name][0]
        shutil.copytree('/Volumes/Micro-Manager/' + latest_build, destination, dirs_exist_ok=True)
        # unmount
        subprocess.run(['hdiutil', 'detach', '/Volumes/Micro-Manager'])
        # delete this installer
        os.remove(installer)
        return destination

        # For issues with M1 Macs: https://github.com/conda-forge/miniforge/issues/165#issuecomment-860233092
