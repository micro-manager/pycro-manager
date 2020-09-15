import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pycromanager",
    version="0.4.10",
    author="Henry Pinkard",
    author_email="henry.pinkard@gmail.com",
    description="Open source microscope control using python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/henrypinkard/pycro-manager",
    packages=setuptools.find_packages(),
    install_requires=['numpy', 'dask[array]>=2.4.0', 'zmq'],
    python_requires='>=3.6',
   
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
	"Programming Language :: Python :: 3.8",		
	"Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",      
        "Operating System :: OS Independent",
    ],
)
