"""
Script for updating pycormanager and its java libraries

version number in library pom and pycromanager pom must be changed manually

this script updates pycromanager to use latest libraries
then updates version numbers in micromanager ivy.xml
"""

from pathlib import Path
import re
import os
import git 



# get latest version numbers of NDTiff, AcqEngJ, NDViewer, PycormanagerJava from their repsective files
versions = {}
git_repos_dir = Path(__file__).parent.parent 
poms = {'NDTiffStorage': '/NDTiffStorage/java/pom.xml',
		'NDViewer': '/NDViewer/pom.xml',
		'AcqEngJ': '/AcqEngJ/pom.xml',
		'PycroManagerJava': '/pycro-manager/java/pom.xml'}

for lib in poms.keys():
	f = str(git_repos_dir) + poms[lib]
	with open(f) as pom_file:
		s = pom_file.read()
		versions[lib] = s.split('<version>')[1].split('</version')[0]


# redeploys = []
# ###### update dependencies in PycroManageJava
# print('Updating PycroManageJava pom')
# f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
# with open(f, 'r') as infile:
#     data = infile.read()

# for lib_name in versions:
# 	new_ver = versions[lib_name]
# 	allf = re.findall('{}</artifactId>\n.*?<version>(.*?)</version>'.format(lib_name), data, )
# 	old_ver = allf[0]
# 	if new_ver != old_ver:
# 		redeploys.append(lib_name)
# 	# if lib_name == 'PycroManagerJava' && old_ver != new_ver:


# 	print('{}:\t\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver))
# 	data = re.sub('{}</artifactId>\n.*?<version>(.*?)</version>'.format(lib_name),
# 		'{}</artifactId>\n     <version>{}</version>'.format(lib_name, new_ver), data, )


# # Rewrite file
# with open(f, 'w') as outfile:
#     outfile.write(data)


####### update dependencies in micro-manager
print('\n\nUpdating micro-manager ivy')
g = git.cmd.Git("{}/micro-manager/".format(str(git_repos_dir)))
g.pull()

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

print('pushing micromanager')
os.system("cd \"{}{}\" && git commit -am \"update libraries\" && git push".format(str(git_repos_dir), '/micro-manager'))







