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

## Testing the code

We use the [pytest](https://docs.pytest.org/) framework to test the code. During development, you can run the tests locally using

```sh
# in the project root directory
pytest -v
```

The suite of [tests](https://github.com/micro-manager/pycro-manager/tree/main/pycromanager/test) also runs automatically using [GitHub Actions](https://github.com/micro-manager/pycro-manager/actions) for every PR. All tests must pass before a PR is merged. Please contribute new tests as you fix bugs and develop new features.

Execution of the `pycro-manager` tests depends on [Micro-manager](https://micro-manager.org/) and several Java libraries ([AcqEngJ](https://github.com/micro-manager/AcqEngJ), [NDTiffStorage](https://github.com/micro-manager/NDTiffStorage), [NDViewer](https://github.com/micro-manager/NDViewer)).

During setup, `pytest` will download the latest [nightly build](https://micro-manager.org/Micro-Manager_Nightly_Builds) of `Micro-manager` and install it in `~/Micro-Manager-nightly`; this step will be skipped if that folder exists. Currently installation of the latest `Micro-manager` nightly build through `pytest` is only supported on Windows platforms. For other platforms, please manually install a working version of `Micro-manager` in `~/Micro-Manager-nightly`.

During setup, `pytest` will also look for pre-compiled `.jar` files in the `../../{java_lib_name}/target` directory (e.g. `../../{AcqEngJ}/target`) and replace the ones that are packaged with the `Micro-manager` nightly build if they are older version. This is helpful when co-developing these libraries. The user does need to pre-compile the Java libraries first. When the tests run in GitHub Actions they always use with the `.jar` files that are packaged with `Micro-manager`. 

Tests of the `pycro-manager` NDViewer and `napari` viewer only execute locally and are skipped by GitHub Actions. When making changes that may affect these viewer, please make sure to always run the tests locally.

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
