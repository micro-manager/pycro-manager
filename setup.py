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
    install_requires=[
        "numpy",
        "dask[array]>=2022.2.0",
        "pyzmq",
        "docstring-inheritance",
        "ndtiff>=1.4.0"
    ],
    python_requires=">=3.6",
    extras_require={
        "test": [
            "pytest",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
