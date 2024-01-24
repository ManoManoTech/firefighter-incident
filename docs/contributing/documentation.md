# Documentation

Substantial contribution must always come with exhaustive documentation. We consider documentation as important as code.
All the documentation for the project FireFighter are in the repository.

If you see mistake or lack of information on a part of the project documentation, you can add it. If it's a technical part, you can add it directly in the code, using inline documentation (see the [development guideline](development.md))

## Documentation Formatting

Although formatting is not enforced on the documentation, feel free to use the [VS Code extension `markdownlint`](https://marketplace.visualstudio.com/items?itemName=DavidAnson.vscode-markdownlint) to keep the Markdown style consistent.

## Running the documentation locally

The documentation is built with [MkDocs](https://www.mkdocs.org/), a static site generator for project documentation.

To serve the documentation locally, run:

```shell
pdm run docs-serve
```

To build the documentation locally, run:

```shell
pdm run docs-build
```
