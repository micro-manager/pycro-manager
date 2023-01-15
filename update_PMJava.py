"""
Called by github actions to update Pycro-ManagerJava version when
one of AcqEngJ, NDTiff, NDViewer changes their versions

If any one of these changes their minor or patch versions, the minor/patch
version will be incremented
"""

import xml.etree.ElementTree as ET
from semantic_version import Version
from pathlib import Path

git_repos_dir = Path(__file__).parent.parent 
print('structure')
print(Path(__file__))
print(Path(__file__).parent)
print(Path(__file__).parent.parent)
poms = {'NDTiffStorage': '/NDTiffStorage/java/pom.xml',
        'NDViewer': '/NDViewer/pom.xml',
        'AcqEngJ': '/AcqEngJ/pom.xml'}
updated_versions = {}

# Get the latest version numbers
for lib in poms.keys():
    f = str(git_repos_dir) + poms[lib]
    tree = ET.parse(f)
    root = tree.getroot()
    updated_versions[lib] = root.find('version').text

# Update the version in PycroManagerJava pom.xml
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
tree = ET.parse(f)
root = tree.getroot()

# Update the dependency versions
print('Dependencies')
minor_version_increased = False
patch_version_increased = False
for lib_name in versions:
    dependency = root.find("./dependencies/dependency[artifactId='{}']".format(lib_name))
    if dependency is not None:
        old_version = dependency.find("version").text
        new_version = updated_versions[lib_name]
        print('\t', lib_name, '\told: ', old_version, '\tnew: ', new_version)
        if Version(new_version) > Version(old_version):
            if Version(new_version).minor > Version(old_version).minor:
                minor_version_increased = True
            elif Version(new_version).patch > Version(old_version).patch:
                patch_version_increased = True
            # Update the version in the xml file
            dependency.find("version").text = new_version
            print('\t\tupdated to version: ', new_version)


print('\nPycroManagerJava')
# Read the PM Java version from the main branch
url = f'https://raw.githubusercontent.com/micro-manager/pycro-manager/main/java/pom.xml'
response = requests.get(url)
root = ET.fromstring(response.text)
current_pm_version = Version(root.find("version").text)

new_version = Version(str(current_pm_version))
if minor_version_increased:
    new_version = new_version.next_minor()
elif patch_version_increased:
    new_version = new_version.next_patch()

if (new_version > current_pm_version):
    print('\t Updated: \told', current_pm_version, '\tnew', new_version)


root.find("version").text = str(new_version)
            
# Resave the xml file
tree.write(f)
