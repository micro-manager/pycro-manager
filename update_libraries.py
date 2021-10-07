from pathlib import Path
import re

# get latest version numbers of NDTiff, AcqEngJ, NDViewer, PycormanagerJava from their repsective files
versions = {}
git_repos_dir = Path(__file__).parent.parent 
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
with open(f) as pom_file:
	s = pom_file.read()
	versions['PycroManagerJava'] = s.split('<version>')[1].split('</version')[0]

f = str(git_repos_dir) + '/NDTiffStorage/pom.xml'
with open(f) as pom_file:
	s = pom_file.read()
	versions['NDTiffStorage'] = s.split('<version>')[1].split('</version')[0]

f = str(git_repos_dir) + '/NDViewer/pom.xml'
with open(f) as pom_file:
	s = pom_file.read()
	versions['NDViewer'] = s.split('<version>')[1].split('</version')[0]

f = str(git_repos_dir) + '/AcqEngJ/pom.xml'
with open(f) as pom_file:
	s = pom_file.read()
	versions['AcqEngJ'] = s.split('<version>')[1].split('</version')[0]



###### update dependencies in PycroManageJava
print('Updating PycroManageJava pom')
f = str(git_repos_dir) + '/pycro-manager/java/pom.xml'
with open(f, 'r') as infile:
    data = infile.read()

for lib_name in versions:
	new_ver = versions[lib_name]
	allf = re.findall('{}.*?\n.*?<version>(.*?)</version>'.format(lib_name), data, )
	old_ver = allf[0]
	for a in allf:
		print(a)
	print('{}:\t\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver))
	new_data = re.sub('{}.*?\n.*?<version>(.*?)</version>'.format(lib_name), new_ver, data, )

# Rewrite file
# with open(f, 'w') as outfile:
#     outfile.write(new_data)


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
	new_data = re.sub('{}:\tCurrent: {}\tNew: {}'.format(lib_name, old_ver, new_ver), new_ver, data, )

	# Rewrite file
with open(f, 'w') as outfile:
    outfile.write(new_data)


#clean and build all libraries



