# Contributing Guide

We welcome your contributions! Please see the provided steps below and never hesitate to contact us.

If you are a new user, we recommend checking out the detailed [Github Guides](https://guides.github.com).

## Setting up a development installation

In order to make changes to `pycro-manager`, you will need to [fork](https://guides.github.com/activities/forking/#fork) the
[repository](https://github.com/pycro-manager/pycro-manager).

If you are not familiar with `git`, we recommend reading up on [this guide](https://guides.github.com/introduction/git-handbook/#basic-git).

Clone the forked repository to your local machine and change directories:
```sh
git clone https://github.com/your-username/pycro-manager.git
cd pycro-manager
```

Set the `upstream` remote to the base `pycro-manager` repository:
```sh
git remote add upstream https://github.com/micro-manager/pycro-manager.git
```

Install the package in editable mode, along with all of the developer tools
```sh
pip install -r requirements.txt
pip install -e .[test]
```


## Making changes

Create a new feature branch:
```sh
git checkout master -b your-branch-name
```

`git` will automatically detect changes to a repository.
You can view them with:
```sh
git status
```

Add and commit your changed files:
```sh
git add my-file-or-directory
git commit -m "my message"
```

### Help us make sure it's you

Each commit you make must have a [GitHub-registered email](https://github.com/settings/emails)
as the `author`. You can read more [here](https://help.github.com/en/github/setting-up-and-managing-your-github-user-account/setting-your-commit-email-address).

To set it, use `git config --global user.email your-address@example.com`.

## Keeping your branches up-to-date

Switch to the `master` branch:
```sh
git checkout master
```

Fetch changes and update `master`:
```sh
git pull upstream master --tags
```

This is shorthand for:
```sh
git fetch upstream master --tags
git merge upstream/master
```

Update your other branches:
```sh
git checkout your-branch-name
git merge master
```

## Sharing your changes

Update your remote branch:
```sh
git push -u origin your-branch-name
```

You can then make a [pull-request](https://guides.github.com/activities/forking/#making-a-pull-request) to `pycro-manager`'s `master` branch.

## Building the docs

1) Add/edit files in the `docs/source` directory
2) Build a local copy by navigating to the `docs` and typing `make clean && make html`. Make sure there are no compilation errors
3) View the locally built version by opening the `docs/build/html/index.html` file
Most web browsers will allow you to preview HTML pages.
Try entering `file:///absolute/path/to/pycro-manager/docs/build/html/index.html` in your address bar.

## Questions, comments, and feedback

If you have questions, comments, suggestions for improvement, or any other inquiries
regarding the project, feel free to open an [issue](https://github.com/micro-manager/pycro-manager/issues).

Issues and pull-requests are written in [Markdown](https://guides.github.com/features/mastering-markdown/#what). You can find a comprehensive guide [here](https://guides.github.com/features/mastering-markdown/#syntax).
