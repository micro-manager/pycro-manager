# Contributing Guide

We welcome your contributions! Please see the provided steps below and never hesitate to contact us.

If you are a new user, we recommend checking out the detailed [Github Docs](https://docs.github.com/).

## Issues

We use [issues](https://github.com/micro-manager/pycro-manager/issues) to track bug reports, feature requests, and user questions. Please use the suggested template when creating a new issue to receive the most relevant feedback.

## Making changes

Changes to `pycro-manager` need to be proposed in a [pull request](https://github.com/micro-manager/pycro-manager/pulls) (PR) to the `main` branch. Please follow the GitHub documentation on [Contributing to projects](https://docs.github.com/en/get-started/quickstart/contributing-to-projects?tool=webui) for instructions on how to fork the repository, make changes, and create a pull request to contribute to the repo.

Please reference open issues that can be addressed by your PR. Please include a description of the bug fix or new feature implemented in the PR.

## Setting up a development installation

`pycro-manager` can be installed in editable mode to allow you to test the changes you have made. We recommend using an environment management tool such as [Conda](https://github.com/conda/conda).

Create a new conda environment with

```sh
conda create -n pycro-manager
conda activate pycro-manager
```

Navigate to the repo directory and install the package in editable mode, along with all of the developer tools

```sh
pip install -e ".[dev]"
```

## Help us make sure it's you

Each commit you make must have a [GitHub-registered email](https://github.com/settings/emails)
as the `author`. You can read more [here](https://help.github.com/en/github/setting-up-and-managing-your-github-user-account/setting-your-commit-email-address).

To set it, use 

```sh
git config --global user.email your-address@example.com
```

## Keeping your fork up-to-date

Make sure your fork stays up-to-date with the latest changes in the main repo by [syncing your fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork).

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
