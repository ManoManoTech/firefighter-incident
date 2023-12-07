# FireFighter

![Python 3.11](https://img.shields.io/badge/python-3.11-blue?style=flat) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

FireFighter is ManoMano's in-house Incident Management Tool.

It helps manage incidents, by automatically creating a Slack channel for communication, and much more.

## Contributing

See [CONTRIBUTING](.github/CONTRIBUTING.md) for details on submitting patches, the contribution workflow and developer's guide.

### Testing

Testing coverage is **very** limited at the moment.

Pytest is used.

```shell
pdm run tests
```

### Code style

```shell
pdm run fmt
pdm run lint
```

Consider checking all dev commands using `pdm run --list`.

## License

FireFighter is under the MIT license. See the [LICENSE](LICENSE) file for details.
