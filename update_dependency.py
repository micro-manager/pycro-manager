"""
Script for updating NDTiff/AcqEngJ/NDViewer to latest version
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import sys
import os

dep_name = sys.argv[1]
git_repos_dir = str(Path(__file__).parent.parent) + '/'

print(git_repos_dir)
print(os.listdir(git_repos_dir))

if('java' in os.listdir(git_repos_dir + dep_name)):
    pom_path = git_repos_dir + 'java/pom.xml'
else:
    pom_path = git_repos_dir + 'pom.xml'


    
# Get the latest version number
tree = ET.parse(pom_path)
root = tree.getroot()
latest_version_number = root.find('version').text

# Update the version in PycroManagerJava pom.xml
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

#Find the dependency element of the library
dependency = root.find("./dependencies/dependency[artifactId='{}']".format(dep_name))
if dependency is not None:
    old_version = dependency.find("version").text
    if old_version != latest_version_number:
        dependency.find("version").text = latest_version_number
        tree.write(f)
        print(f"{dep_name} version updated from {old_version} to {latest_version_number} in {f}")
    else:
        print("{dep_name} version is already up to date")
else:
    raise Exception(f'cant find {dep_name} in pom.xml')
