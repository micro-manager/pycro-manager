# Adapted from https://github.com/jyksnw/install-jdk/blob/master/jdk/__init__.py
"""
MIT License

Copyright (c) 2020 Jason Snow

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import os
import cgi
import zipfile
import tarfile
import lzma
import shutil
import tempfile

from collections import namedtuple
from subprocess import run
from urllib import request
from sys import platform, maxsize
from os import path

_IS_WINDOWS = os.name == "nt"
_IS_DARWIN = platform == "darwin"
_UNPACK200 = "unpack200.exe" if _IS_WINDOWS else "unpack200"
_UNPACK200_ARGS = '-r -v -l ""' if _IS_WINDOWS else ""
_USER_DIR = path.expanduser("~")
_JRE_DIR = path.join(_USER_DIR, ".jre")
_JDK_DIR = path.join(_USER_DIR, ".jdk")

OS = "windows" if _IS_WINDOWS else "mac" if _IS_DARWIN else platform
ARCH = "x64" if maxsize > 2 ** 32 else "x32"

_Path = namedtuple("_Path", "dir base name ext")

_TAR = ".tar"
_TAR_GZ = ".tar.gz"
_ZIP = ".zip"
_SEVEN_ZIP = ".7z"


class Implementation:

    OPENJ9 = "openj9"
    HOTSPOT = "hotspot"


def normalize_version(version: str) -> str:
    if version == "1.8":
        return "8"
    return version


def get_download_url(
    version: str,
    operating_system: str = OS,
    arch: str = ARCH,
    impl: str = Implementation.HOTSPOT,
    jre: bool = False,
) -> str:

    version = normalize_version(version)
    if jre:
        return f"https://api.adoptopenjdk.net/v3/binary/latest/{version}/ga/{operating_system}/{arch}/jre/{impl}/normal/adoptopenjdk"
    else:
        return f"https://api.adoptopenjdk.net/v3/binary/latest/{version}/ga/{operating_system}/{arch}/jdk/{impl}/normal/adoptopenjdk"


def _get_normalized_compressed_file_ext(file: str) -> str:
    if file.endswith(_TAR):
        return _TAR
    elif file.endswith(_TAR_GZ):
        return _TAR_GZ
    elif file.endswith(_ZIP):
        return _ZIP
    else:
        return _SEVEN_ZIP


def _extract_files(file: str, file_ending: str, destination_folder: str) -> str:
    if path.isfile(file):
        start_listing = set(os.listdir(destination_folder))

        if file_ending == _TAR:
            with tarfile.open(file, "r:") as tar:
                tar.extractall(path=destination_folder)
        elif file_ending == _TAR_GZ:
            with tarfile.open(file, "r:gz") as tar:
                tar.extractall(path=destination_folder)
        elif file_ending == _ZIP:
            with zipfile.ZipFile(file) as z:
                z.extractall(path=destination_folder)
        elif file_ending == _SEVEN_ZIP:
            with lzma.open(file) as z:
                z.extractall(path=destination_folder)

        end_listing = set(os.listdir(destination_folder))
        jdk_directory = next(iter(end_listing.difference(start_listing)))

        return path.join(destination_folder, jdk_directory)


def _path_parse(file_path: str) -> _Path:
    dirname = path.dirname(file_path)
    base = path.basename(file_path)
    name, ext = path.splitext(base)
    return _Path(dir=dirname, base=base, name=name, ext=ext)


def _unpack_jars(fs_path: str, java_bin_path: str) -> None:
    if path.exists(fs_path):
        if path.isdir(fs_path):
            for f in os.listdir(fs_path):
                current_path = path.join(fs_path, f)
                _unpack_jars(current_path, java_bin_path)
        else:
            file_name, file_ext = path.splitext(fs_path)
            if file_ext.endswith("pack"):
                p = _path_parse(fs_path)
                name = path.join(p.dir, p.name)
                tool_path = path.join(java_bin_path, _UNPACK200)
                run([tool_path, _UNPACK200_ARGS, f"{name}.pack", f"{name}.jar"])


def _decompress_archive(
    repo_root: str, file_ending: str, destination_folder: str
) -> str:
    if not path.exists(destination_folder):
        os.mkdir(destination_folder)

    jdk_file = path.normpath(repo_root)

    if path.isfile(jdk_file):
        jdk_directory = _extract_files(jdk_file, file_ending, destination_folder)
        jdk_bin = path.join(jdk_directory, "bin")
        _unpack_jars(jdk_directory, jdk_bin)

        return jdk_directory
    elif path.isdir(jdk_file):
        return jdk_file


def _download(download_url):
    req = request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})

    jdk_file = None
    with request.urlopen(req) as open_request:
        info = open_request.info()
        if "Content-Disposition" in info:
            content_disposition = info["Content-Disposition"]
            _, params = cgi.parse_header(content_disposition)
            if "filename" in params:
                jdk_file = params["filename"]
                jdk_file = path.join(tempfile.gettempdir(), jdk_file)

                with open(jdk_file, "wb") as out_file:
                    shutil.copyfileobj(open_request, out_file)
    return jdk_file


# def install(
#     version: str,
#     operating_system: str = OS,
#     arch: str = ARCH,
#     impl: str = Implementation.HOTSPOT,
#     jre: bool = False,
#     path: str = None,
# ) -> str:
#     url = get_download_url(version, operating_system, arch, impl, jre)
#
#     if not path:
#         path = _JRE_DIR if jre else _JDK_DIR
#
#     jdk_file = None
#     try:
#         jdk_file = _download(url)
#         jdk_ext = _get_normalized_compressed_file_ext(jdk_file)
#         jdk_dir = _decompress_archive(jdk_file, jdk_ext, path)
#
#         return jdk_dir
#     finally:
#         if jdk_file:
#             os.remove(jdk_file)


# TODO: which version??
def install_jre(url='https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/'
                    'download/jdk8u282-b08/OpenJDK8U-jdk_x64_windows_hotspot_8u282b08.zip'):
    jdk_file = None
    try:
        jdk_file = _download(url)
        jdk_ext = _get_normalized_compressed_file_ext(jdk_file)
        jdk_dir = _decompress_archive(jdk_file, jdk_ext, _JRE_DIR)
    finally:
        if jdk_file:
            os.remove(jdk_file)
    return jdk_file


def uninstall(version: str, jre: bool = False):
    version = f"jdk{version}"
    if jre:
        versions = (v for v in os.listdir(_JRE_DIR) if version in v.replace("-", ""))
        for v in versions:
            shutil.rmtree(path.join(_JRE_DIR, v))
    else:
        versions = (v for v in os.listdir(_JDK_DIR) if version in v.replace("-", ""))
        for v in versions:
            shutil.rmtree(path.join(_JDK_DIR, v))