"""
Script for updating NDTiff to latest version
"""

from pathlib import Path
import re
import os
import git 



# get latest version numbers of NDTiff, AcqEngJ, NDViewer, PycormanagerJava from their repsective files
versions = {}
git_repos_dir = Path(__file__).parent.parent 
poms = {'NDTiffStorage': '/NDTiffStorage/java/pom.xml'}

for lib in poms.keys():
	f = str(git_repos_dir) + poms[lib]
	with open(f) as pom_file:
		s = pom_file.read()
		versions[lib] = s.split('<version>')[1].split('</version')[0]


redeploys = []
# ###### update dependencies in PycroManageJava
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
	# if lib_name == 'PycroManagerJava' && old_ver != new_ver:


	print('{}:\t\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver))
	data = re.sub('{}</artifactId>\n.*?<version>(.*?)</version>'.format(lib_name),
		'{}</artifactId>\n     <version>{}</version>'.format(lib_name, new_ver), data, )


# Rewrite file
with open(f, 'w') as outfile:
    outfile.write(data)



