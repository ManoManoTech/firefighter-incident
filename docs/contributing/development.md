# Development

We want to make contributing straightforward and easy for everyone. As such and unless otherwise stated we will use the traditional Github fork and pull workflow: any commit must be made to a feature/topic branch in a local fork and submitted via a merge request before it can be merged.
It is **strongly advised** to open a discussion or an issue **before** working on implementing a new feature or making any kind of large code refactoring.


*Issues and merge requests should be in English.*

## Git

Make sure you have a [GitHub account](https://github.com/join).
The *main* branch should be considered as the production/deploy branch.

#### Forking workflow

> Extensive information can be found in this excellent [forking workflow
> tutorial](https://www.atlassian.com/git/tutorials/comparing-workflows#forking-workflow).

In a nutshell:

1. [Fork](https://help.github.com/articles/fork-a-repo) the repository and clone it locally.

    ```bash
    git clone https://github.com/${USERNAME}/firefighter-incident
    cd firefighter-incident
    ```

2. Create a topic branch where changes will be done.

    ```bash
    git checkout -b ${MY_TOPIC_BRANCH}
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

    > You may loosely follow [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) if you want to.

4. Add test if needed & make sure the test suite and various linters are passing.

5. Push the topic branch to the remote forked repository.

    ```bash
    git push origin ${MY_TOPIC_BRANCH}
    ```

6. [Open a Pull Request](https://github.com/ManoManoTech/firefighter-incident/pulls) to merge your code and its documentation. The earlier you open a merge request, the sooner you can get feedback.

7. Verify the test suite is passing in the CI & verify if the pipeline is green.

8. Once the PR has been merged, the topic branch can be removed from the local fork.

    ```bash
    git branch -d ${MY_TOPIC_BRANCH}
    git push origin --delete ${MY_TOPIC_BRANCH}
    ```


### Syncing a fork with its upstream

This is used to keep a local fork up-to-date with the original upstream repository.

1. Connect the local to the original upstream repository.

    ```
    git remote add upstream https://github.com/${USERNAME}/${REPONAME}
    ```

2. Checkout, fetch and merge the upstream master branch to the local one.

    ```
    git checkout main
    git fetch upstream
    git merge upstream/master
    ```

3. Push changes to update to remote forked repository.

    ```
    git push
    ```

See [GitHub help](https://help.github.com/articles/syncing-a-fork) for more information.

## Dev tooling

Check all available commands using `pdm run --list`.

### Package Management

We use PDM with specific scripts for different environments:

**Local Development:**
```shell
# Install for local development (includes dev dependencies)
pdm install

# Build local package for testing
pdm build

# Install built package locally
pip install dist/firefighter_incident-*.whl
```

**Production Package:**
```shell
# Build production package
pdm run build-web  # Build frontend assets first
pdm build --no-sdist  # Build wheel only

# Publish to PyPI (maintainers only)
pdm publish
```

### Web Assets Development

FireFighter includes frontend assets (CSS/JS) that need to be built:

```shell
# Build CSS/JS assets for development
pdm run build-web

# Watch for changes (if you're working on frontend)
npm run dev  # or directly: rollup -c --watch
```

**Asset Pipeline:**
- **CSS**: Tailwind CSS → PostCSS → Minified CSS
- **JavaScript**: ES6+ → Rollup → Bundled JS
- **Assets**: Copied to `src/firefighter/static/`

### Environment Scripts

**Development Environment:**
```shell
pdm run dev-env-setup    # Complete setup (recommended for first time)
pdm run dev-env-start    # Start services only
pdm run dev-env-stop     # Stop services
pdm run dev-env-destroy  # ⚠️ Nuclear option - destroys DB!
```

**Application:**
```shell
pdm run runserver       # Django development server
pdm run celery-worker   # Background task worker
pdm run celery-beat     # Task scheduler
```

### Formatting

We use `ruff`. You can run `pdm run fmt` or `ruff format .` in the project root to format every file.

```shell
pdm run fmt
```

> This is the equivalent of running `ruff format .` in the project root.

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

Read more in [the documentation contribution docs](documentation.md).

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
