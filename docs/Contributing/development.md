# Development

We want to make contributing straightforward and easy for everyone. As such and unless otherwise stated we will use the traditional GitLab fork and pull workflow: any commit must be made to a feature/topic branch in a local fork and submitted via a merge request before it can be merged.
It is **strongly advised** to contact the project owner(s) (Pulse team) **before** working on implementing a new feature or making any kind of large code refactoring.

## Global principe

- All merge request must be attached to Jira ticket, in the [FireFighter board](https://manomano.atlassian.net/secure/RapidBoard.jspa?rapidView=443)
- Issues and merge requests should be in English.

## Step to start contributing

<!-- XXX Updated documentation for OSS -->

1. Create a public fork of the FireFighter project

    ```bash
    git clone git@git.manomano.tech:pulse/incident-management/firefighter.git
    cd firefighter
    ```

2. Create a topic branch where changes will be done. The topic branch must contain the ref of the Jira ticket

    ```bash
    git checkout -b ${FIR-XXX_TOPIC_BRANCH}
    ```

3. Commit the changes in logical and incremental chunks and use
   [interactive rebase](https://help.github.com/articles/about-git-rebase)
   when needed.
   In your
   [commit messages](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html),
   make sure to:
    - use the present tense
    - use the imperative mood
    - limit the first line to 72 characters
    - reference any associated issues and/or PRs (if applicable)

    ```bash
    git commit -am 'Add new feature...'
    ```

4. Add test if needed & make sure the test suite is passing.

5. Push the topic branch to the remote forked repository.

    ```bash
    git push origin ${FIR-XXX_TOPIC_BRANCH}
    ```

6. [Open a Merge Request](https://docs.gitlab.com/ee/gitlab-basics/add-merge-request.html) to merge your code and its documentation. The earlier you open a merge request, the sooner you can get feedback.

7. Verify the test suite is passing in the CI & verify if the pipeline is green.

8. Once the PR has been merged, the topic branch can be removed from the local fork.

    ```bash
    git branch -d ${FIR-XXX_TOPIC_BRANCH}
    git push origin --delete ${FIR-XXX_TOPIC_BRANCH}
    ```

## Dev tooling

Check all available commands using `pdm run --list`.

### Formatting

We use `black`. You can run `pdm run fmt` or `black .` in the project root to format every file.

```shell
pdm run fmt
```

> This is the equivalent of running `black .` in the project root.

Import sorting managed by `ruff`.

### Linting

`ruff`, `pylint` and `mypy` are configured.

```shell
pdm run lint-ruff
```


```shell
pdm run lint-pylint
```

> This is the equivalent of running `pylint --django-settings-module=firefighter.settings <our_sources>` in the project root.

!!! note
    We are progressively disabling Pylint checks that are implemented by `ruff`.

```shell
pdm run lint-mypy
```

> This is the equivalent of running `mypy <our_sources>` in the project root.

!!! warning
    The lint checks won't pass, as they are still some issues/false positives that needs to be fixed.

### Testing

```shell
pdm run tests
```

> This is the equivalent of running `pytest tests` in the project root.

!!! warning
    The testing coverage is still very low.

### Documentation

```shell
pdm run docs-serve
```

> This is the equivalent of running `mkdocs serve` in the project root.
// TODO Pre-commit hook

## Conventions

### Code style

We loosely follow the [PEP8](https://www.python.org/dev/peps/pep-0008/) style guide and Google's [Python Style Guide](https://google.github.io/styleguide/pyguide.html).

Use your best judgement when deciding whether to break the rules.

### Imports

Import sorting is managed by `ruff`. Absolute imports are enforced.

### Docstrings

We use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

You can link to other classes, methods, functions, or modules by using the [mkdocstrings cross-reference](https://mkdocstrings.github.io/usage/#cross-references) syntax:

```markdown
With a custom title:
[`Object 1`][full.path.object1]

With the identifier as title:
[full.path.object2][]
```

You can cross-reference to the Python standard library and Django objects.
