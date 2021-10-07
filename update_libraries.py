"""
Script for updating pycormanager and its java libraries

version number in library pom and pycromanager pom must be changed manually

this script updates pycromanager to use latest libraries, maven updates all applicable, 
then updates version numbers in micromanager
"""

from pathlib import Path
import re
import os

# get latest version numbers of NDTiff, AcqEngJ, NDViewer, PycormanagerJava from their repsective files
versions = {}
git_repos_dir = Path(__file__).parent.parent 
poms = {'NDTiffStorage': '/NDTiffStorage/pom.xml',
		'NDViewer': '/NDViewer/pom.xml',
		'AcqEngJ': '/AcqEngJ/pom.xml',
		'PycroManagerJava': '/pycro-manager/java/pom.xml'}

for lib in poms.keys():
	f = str(git_repos_dir) + poms[lib]
	with open(f) as pom_file:
		s = pom_file.read()
		versions[lib] = s.split('<version>')[1].split('</version')[0]


redeploys = []
###### update dependencies in PycroManageJava
print('Updating PycroManageJava pom')
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
with open(f, 'r') as infile:
    data = infile.read()

for lib_name in versions:
	new_ver = versions[lib_name]
	allf = re.findall('{}</artifactId>\n.*?<version>(.*?)</version>'.format(lib_name), data, )
	old_ver = allf[0]
	if new_ver != old_ver:
		redeploys.append(lib_name)
	# for a in allf:
	# 	print(a)
	print('{}:\t\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver))
	data = re.sub('{}</artifactId>\n.*?<version>(.*?)</version>'.format(lib_name),
		'{}</artifactId>\n         <version>{}</version>'.format(lib_name, new_ver), data, )


# Rewrite file
with open(f, 'w') as outfile:
    outfile.write(data)


#always redeploy pycormanage, since it wont be detected as changed by the above script but it always will change
if 'PycroManagerJava' not in redeploys:
	redeploys.append('PycroManagerJava')
#maven deploys
for lib_name in redeploys:
	folder_name = Path(str(git_repos_dir) + poms[lib]).parent
	os.system('cd {} && mvn clean && mvn deploy'.format(folder_name))


####### update dependencies in micro-manager
print('\n\nUpdating micro-manager ivy')
f = str(git_repos_dir) + '/micro-manager/buildscripts/ivy.xml'
with open(f, 'r') as infile:
    data = infile.read()
for lib_name in versions:
	new_ver = versions[lib_name]
	allf = re.findall('name=\"{}\".*?rev=\"(.*?)\"'.format(lib_name), data, )
	old_ver = allf[0]
	# for a in allf:
	# 	print(a)
	print('{}:\t\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver))
	data = re.sub('name=\"{}\".*?rev=\"(.*?)\"'.format(lib_name, old_ver, new_ver),
				'name=\"{}\" rev=\"{}\"'.format(lib_name, new_ver), data, )

	# Rewrite file
with open(f, 'w') as outfile:
    outfile.write(data)





