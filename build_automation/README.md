The following is the flow of actions and checks that occurs to automate continuous integration of the Java parts of NDTiffStorage, NDViewer, AcqEngJ and PycroManagerJava into Micro-Manager

**1. PR to main branch of NDTiffStorage, AcqEngJ, or NDViewer triggers [maven_deployment_and_pm_update.yml](https://github.com/micro-manager/NDTiffStorage/blob/main/.github/workflows/maven_deployment_and_pm_update.yml)**
- which builds a new version of the project and deploys it to maven central
- Then runs pycro-manager's [update_dependency.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_dependency.py) script
  - which waits for the new jar to become available
  - and then updates only that dependency in pycromanagers POM.xml in the dependency-update branch
- and pushes the changed pom.xml to the dependency-update branch of pycro-manager

**2. Push to pycro-manager's depedency-update branch triggers [Java_dependency_update.yml](https://github.com/micro-manager/pycro-manager/blob/main/.github/workflows/Java_dependency_update.yml)**
- which calls [update_PycroManagerJava.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_PycroManagerJava.py)
  - which increments the version of PycroManagerJava as needed based on its updated dependencies
- and pushes the update to the dependency-update branch of pycro-manager
  - (Somehow this doesn’t trigger ****Java_dependency_update.yml…?****)
- and opens an automerging pull request from the dependency-update branch onto main

(Note: if only the version of PycroManagerJava changes, the process begins here)

**3. PR to main triggers pycro-manager's tests to make sure everything is working with new dependencies. If it passes, it is merged and then triggers [maven_deploy_and_mm_update.yml](https://github.com/micro-manager/pycro-manager/blob/main/.github/workflows/maven_deploy_and_mm_update.yml)**
- which deploys a new maven version of Pycro-ManagerJava
- and calls [update_mm_ivy.py](https://github.com/micro-manager/pycro-manager/blob/main/build_automation/update_mm_ivy.py)
  - Which updates versions of PycroManagerJava, NDTiffStorage, NDViewer in the ivy.xml file of micromanager
  - And waits for the new PycroManagerJava.jar to become available on maven central
- Then pushes to the dependency-update branch of micro-manager
- And opens an automerge pull request to main branch of micro-manager, which if all status checks pass, merges into the main branch of micro-manager
