# IMPACT

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Imports: ruff/isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/) [![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit) ![Python 3.11](https://img.shields.io/badge/python-3.11-blue?style=flat)

IMPACT is the ManoMano's in-house Incident Management Tool.

It helps manage incidents, by automatically creating a Slack channel for communication, and much more.

## Contributing

Checkout the Contributing documentation in `docs/Contributing`, for an in-depth installation guide.




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
