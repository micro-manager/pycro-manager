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

def _find_versions():
    """
    Find all available versions of Micro-Manager nightly builds
    """
    platform = _get_platform()
    # Get the webpage
    if platform == 'Windows':
        webpage = requests.get(MM_DOWNLOAD_URL_WINDOWS)
    elif platform == 'Mac':
        webpage = requests.get(MM_DOWNLOAD_URL_MAC)
    else:
        raise ValueError(f"Unsupported OS: {platform}")
    return re.findall(r'class="rowDefault" href="([^"]+)', webpage.text)


def download_and_install(destination='auto', mm_install_log_path=None):
    """
    Download and install the latest nightly build of Micro-Manager

    Parameters
    ----------
    destination : str
        The directory to install Micro-Manager to. If 'auto', it will install to the user's home directory.

    Returns
    -------
    str
        The path to the installed Micro-Manager directory
    """
    windows = _get_platform() == 'Windows'
    platform = 'Windows' if windows else 'Mac'
    installer = 'mm_installer.exe' if windows else 'mm_installer.dmg'
    latest_version = MM_DOWNLOAD_URL_BASE + _find_versions()[0]
    # make a progress bar that updates every 0.5 seconds
    def bar(curr, total, width):
        if not hasattr(bar, 'last_update'):
            bar.last_update = 0
        if curr / total*100 - bar.last_update > 0.5:
            print(f"\rDownloading installer: {curr / total*100:.2f}%", end='')
            bar.last_update = curr / total*100
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
            destination = os.path.expanduser('~') + '/Micro-Manager'
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
