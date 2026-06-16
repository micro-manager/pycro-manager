import setuptools
from os import path

with open("README.md", "r") as fh:
    long_description = fh.read()

# extract version
path = path.realpath("pycromanager/_version.py")
version_ns = {}
with open(path, encoding="utf8") as f:
    exec(f.read(), {}, version_ns)
version = version_ns["__version__"]

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="pycromanager",
    version=version,
    author="Henry Pinkard",
    author_email="henry.pinkard@gmail.com",
    description="Open source microscope control using python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/micro-manager/pycro-manager",
    packages=setuptools.find_packages(),
    install_requires=requirements,
    python_requires=">=3.10",
    extras_require={
        "dev": [
            "pytest",
            "wget",
            "requests",
            "napari"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
