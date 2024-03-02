# FireFighter Telemetry

## Logging

FireFighter uses the [logging](https://docs.python.org/3/library/logging.html) module to log messages to the console and to a file.

### Default modes

#### Production JSON

FireFighter logs to stdout using [loggia](https://github.com/ManoManoTech/loggia) and its [JSON Formatter][loggia.stdlib_formatters.json_formatter.CustomJsonFormatter].

The JSON formats adheres to DataDog's [JSON log format](https://docs.datadoghq.com/logs/log_collection/python/?tab=standard#json-format).

#### Development

In development mode, FireFighter logs to the console using [loggia](https://github.com/ManoManoTech/loggia)'s [Pretty formatter][loggia.stdlib_formatters.pretty_formatter.PrettyFormatter]

### Further Configuration

You should check [loggia's documentation](https://manomanotech.github.io/loggia/latest/config/) for more details.

Loggia can mostly be configured using environment variables.

You can configure the logging manually by editing the `LOGGING` Python setting, or by running your configuration code in your custom settings.

## Tracing

FireFighter use Datadog's [ddtrace](https://ddtrace.readthedocs.io/en/stable/index.html). Most configuration can be passed as environment variables.
