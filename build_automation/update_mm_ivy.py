"""
This script reads the versions of pycromanager and its dependencies from the pom file 
and makes updates to the micro-manager ivy.xml file
It runs upon changes to the java/pom.xml file of the main branch
"""

import xml.etree.ElementTree as ET
from lxml import etree
from semantic_version import Version
from pathlib import Path
import requests
import time
import re

def read_versions(root):
    versions = {}
    versions['PycroManagerJava'] = Version(root.find("version").text)
    # iterate through the dependencies and get NDStorage, NDViewer, and AcqEngJ
    dependencies = root.findall(".//dependency")
    for dependency in dependencies:
        artifactId = dependency.find("artifactId").text
        version = dependency.find("version").text
        if artifactId in ["NDStorage", "NDViewer", "AcqEngJ"]:
            versions[artifactId] = Version(version)
    return versions

git_repos_dir = Path(__file__).parent.parent.parent
ivy_path = str(git_repos_dir) + '/micro-manager/buildscripts/ivy.xml'
  
# Read from pom.xml in pycromanager
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

updated_versions = read_versions(root)


#Update the version numbers in the ivy file
with open(ivy_path, 'r') as file:
    xml = file.read()

# Use regular expression to search for name and rev attributes
matches = re.finditer(r'name="([^"]*)" rev="[^"]*"', xml)

# Iterate through the matches and replace the rev attribute with the corresponding value from the dictionary
for match in matches:
    name = match.group(1)
    if name in updated_versions:
        new_rev = updated_versions[name]
        xml = xml.replace(match.group(), 'name="{}" rev="{}"'.format(name, new_rev))

with open(ivy_path, 'w') as file:
    file.write(xml)

    
# Wait for PycroManagerJava to become available, because there is a delay after it is deployed
dep_name = 'PycroManagerJava'
latest_version_number = str(updated_versions[dep_name])
url = f"https://repo.maven.apache.org/maven2/org/micro-manager/pycro-manager/{dep_name}/{latest_version_number}/{dep_name}-{latest_version_number}.jar"
# url = f"https://s01.oss.sonatype.org/service/local/repositories/releases/content/org/micro-manager/pycro-manager/{dep_name}/{latest_version_number}/{dep_name}-{latest_version_number}.jar"

start = time.time()
while True:
    response = requests.head(url)
    if response.status_code == 200:
        break
    else:
        print(f"waiting for {dep_name}-{latest_version_number} for {time.time() - start} s\r", end='')
        time.sleep(5)
print('Dependency available')
