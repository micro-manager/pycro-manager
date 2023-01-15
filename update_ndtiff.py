"""
Script for updating NDTiff to latest version
"""

import xml.etree.ElementTree as ET
from pathlib import Path

git_repos_dir = Path(__file__).parent.parent 
poms = {'NDTiffStorage': '/NDTiffStorage/java/pom.xml'}
versions = {}

# Get the latest version numbers
for lib in poms.keys():
    f = str(git_repos_dir) + poms[lib]
    tree = ET.parse(f)
    root = tree.getroot()
    versions[lib] = root.find('version').text

# Update the version in PycroManagerJava pom.xml
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

#Find the dependency element of NDTiffStorage
dependency = root.find("./dependencies/dependency[artifactId='NDTiffStorage']")
if dependency is not None:
    old_version = dependency.find("version").text
    new_version = versions['NDTiffStorage']
    if old_version != new_version:
        dependency.find("version").text = new_version
         tree.write(f)
        print(f"NDTiffStorage version updated from {old_version} to {new_version} in {f}")
    else:
        print("NDTiffStorage version is already up to date")
else:
    print(f"NDTiffStorage is not being used by PycroManagerJava. No update needed")
