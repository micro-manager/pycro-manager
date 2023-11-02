---
name: Bug Report
about: Report a bug in pycro-manager
labels: bug
---


<!--Before submitting a bug report, make sure you have 
    1) installed the latest version of pycromanager (pip install pycromanager --upgrade) 
    2) are using the latest nightly build of micro-manager
    -->

<!--Note that many times things that may appear to be bugs in pycro-manager are 
    actually coming from the micro-manager core or the device adapters for the hardware in use.
    If this is the case, you should instead open a bug in the main micro-manager repository 
    (https://github.com/micro-manager/micro-manager). To check this, try reproducing your 
    bug using the micro-manager demo configuration, which comes with every micro-manager installation
    and provides simulated "demo" hardware. If you can't reproduce your issue with the demo
    configuration, it is likely unrelated to pycro-manager
    -->

<!--The best bug reports are those which can be converted into an automated test. 
This ensures that once fixed, the bug can be avoided in the future. Tests are minimal 
scripts that reproduce the errant behavior using the Micro-Manager Demo configuration.
Examples of tests can be found here: 
https://github.com/micro-manager/pycro-manager/tree/main/pycromanager/test
-->

<!--If you're familiar with the process of making pull requests, the most helpful type of
bug report to create is one with a linked pull request with a new test added (which should 
currently fail due to the bug). More information running the testing framework can be found here:
(https://github.com/micro-manager/pycro-manager/blob/main/Contributing.md#testing-the-code). 
If you're not familiar with this process, it is also okay to simply paste a snippet of 
code in this report.-->

**Code for reproduction**
```python
# your code here
```

**Expected outcome**

<!--A description of the expected outcome from the code snippet-->

**Actual outcome**

<!--The output produced by the above code, which may be a screenshot, console output, etc.-->

