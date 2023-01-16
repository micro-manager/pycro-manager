"""
Script for updating NDTiff/AcqEngJ/NDViewer to latest version
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import sys
import os
import requests
import time

dep_name = sys.argv[1]
git_repos_dir = str(Path(__file__).parent.parent) + '/'


if('java' in os.listdir(git_repos_dir + dep_name)):
    pom_path = git_repos_dir + dep_name + '/java/pom.xml'
else:
    pom_path = git_repos_dir + dep_name + '/pom.xml'

    
# Get the latest version number
tree = ET.parse(pom_path)
root = tree.getroot()
latest_version_number = root.find('version').text

# Wait for the version to become available, because there is a delay after it is deployed
url = f"https://s01.oss.sonatype.org/service/local/repositories/releases/content/org/micro-manager/{dep_name.lower()}/{dep_name}/{latest_version_number}/{dep_name}-{latest_version_number}.jar"

start = time.time()
while True:
    response = requests.head(url)
    if response.status_code == 200:
        break
    else:
        print(f"waiting for {dep_name}-{latest_version_number} for {time.time() - start} s\r", end='')
        time.sleep(5)
print('Dependency available')


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
