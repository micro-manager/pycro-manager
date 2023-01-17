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

def read_versions(root):
    versions = {}
    versions['PycroManagerJava'] = Version(root.find("version").text)
    # iterate through the dependencies and get NDTiff, NDViewer, and AcqEngJ
    dependencies = root.findall(".//dependency")
    for dependency in dependencies:
        artifactId = dependency.find("artifactId").text
        version = dependency.find("version").text
        if artifactId in ["NDTiffStorage", "NDViewer", "AcqEngJ"]:
            versions[artifactId] = Version(version)
    return versions

git_repos_dir = Path(__file__).parent.parent.parent
ivy_path = str(git_repos_dir) + '/micro-manager/buildscripts/ivy.xml'
  
# Read from pom.xml in pycromanager
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

updated_versions = read_versions(root)


def modify_rev(xml_str, updated_versions):
    root = etree.fromstring(xml_str)
    dependencies = {
        "org.micro-manager.ndviewer": {"name":"NDViewer"},
        "org.micro-manager.acqengj": {"name":"AcqEngJ"},
        "org.micro-manager.ndtiffstorage": {"name":"NDTiffStorage"},
        "org.micro-manager.pycro-manager": {"name":"PycroManagerJava"},
    }

    for dependency in root.iter("dependency"):
        if "org" not in dependency.attrib:
            continue
        org = dependency.attrib["org"]
        name = dependency.attrib["name"]
        if org in dependencies and name == dependencies[org]["name"]:
            new_version = str(updated_versions[dependencies[org]["name"]])
            print(dependencies[org]["name"], '\t', dependency.attrib["rev"],  'to\t', new_version)
            dependency.attrib["rev"] = new_version
    return etree.tostring(root, pretty_print=True).decode()


with open(ivy_path, 'r') as f:
    xml_str = f.read()

modified_xml_str = modify_rev(xml_str, updated_versions)

with open(ivy_path, 'w') as f:
    f.write(modified_xml_str)
    
    
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
