The following is the flow of actions and checks that occurs to automate continuous integration of the Java parts of NDTiffStorage, NDViewer, AcqEngJ and PycroManagerJava into Micro-Manager, and updates to the pycromanager python package

**1. PR to main branch of NDTiffStorage, AcqEngJ, or NDViewer triggers [maven_deployment_and_pm_update.yml](https://github.com/micro-manager/NDTiffStorage/blob/main/.github/workflows/maven_deployment_and_pm_update.yml)**
- which builds a new version of the project and deploys it to maven central
- Then creates a new branch in pycro-manager
- Then runs pycro-manager's [update_dependency.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_dependency.py) script
  - which waits for the new jar to become available
  - then updates the version of the dependency in the pom.xml
- Then runs pycro-manager's [update_PycroManagerJava.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_PycroManagerJava.py)
  - Which bumps the pycro-manager version to refelct the new dependency
- Then opens a PR to the main branch of micro-manager and waits for it to merge

_(Note: if only the version of PycroManagerJava changes, the process begins here)_

**2. PR into main branch of pycro-manager triggers pycro-manager's tests to make sure everything is working with new dependencies. If it passes, it is merged and then triggers [build_and_deploy.yml](https://github.com/micro-manager/pycro-manager/blob/main/.github/workflows/build_and_deploy.yml)**
- which deploys a new maven version of Pycro-ManagerJava
- then calls [update_mm_ivy.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_mm_ivy.py)
  - Which updates versions of PycroManagerJava, NDTiffStorage, NDViewer, AcqEngJ in the ivy.xml file of micromanager
  - And waits for the new PycroManagerJava.jar to become available on maven central
- Then commits these changes to a new temporary branch of micro-manager, and opens an automerging PR. Once all status checks pass and the PR has merged, then the action checks if a the python version of pycro-manager has been updated and deploys a new version to pypi as needed
