import xml.etree.ElementTree as ET
from semantic_version import Version
from pathlib import Path
import requests

def read_versions(root):
    versions = {}
    versions['PycroManagerJava'] = Version(root.find("version").text)
    # iterate through the dependencies and get NDStorage, NDViewer, and AcqEngJ
    dependencies = root.findall(".//dependency")
    for dependency in dependencies:
        artifactId = dependency.find("artifactId").text
        version = dependency.find("version").text
        if artifactId in ["NDTiffStorage", "NDViewer", "AcqEngJ"]:
            versions[artifactId] = Version(version)
    return versions

git_repos_dir = Path(__file__).parent.parent.parent

# Read the copy of the pom on the dependencies branch
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

updated_versions = read_versions(root)


# Read the the versions currently on the main branch
url = f'https://raw.githubusercontent.com/micro-manager/pycro-manager/main/java/pom.xml'
response = requests.get(url)
root = ET.fromstring(response.text)

main_branch_versions = read_versions(root)


# Compare these versions to the main branch in order to figure out what updates have occured
minor_version_increased = False
patch_version_increased = False
for lib_name in main_branch_versions.keys():
    old_version = main_branch_versions[lib_name]
    new_version = updated_versions[lib_name]
    print('\t', lib_name, '\t\told: ', old_version, '\tnew: ', new_version)
    if new_version > old_version:
        if new_version.minor > old_version.minor:
            minor_version_increased = True
        elif new_version.patch > old_version.patch:
            patch_version_increased = True
    elif old_version > new_version:
        raise Exception('The main branch version of {} is greater than the '
                        'dependency branch. something has gone wrong'.format(lib_name))

if updated_versions['PycroManagerJava'] > main_branch_versions['PycroManagerJava']:
    pm_version = updated_versions['PycroManagerJava']
else:
    pm_version = main_branch_versions['PycroManagerJava']
    
if minor_version_increased or patch_version_increased:
#     pm_version = pm_version.next_minor()
# elif patch_version_increased:
    pm_version = pm_version.next_patch()

    
# Resave dependecies branch pom with latest versions
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()
dependency = root.find("version").text
# Update the version in the xml file
root.find("version").text = str(pm_version)
print('\t\tupdated to version: ', pm_version)

         
# Resave the xml file
tree.write(f)
