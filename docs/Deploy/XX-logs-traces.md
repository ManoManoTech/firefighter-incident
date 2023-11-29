# FireFighter Telemetry

## Logging

FireFighter uses the [logging](https://docs.python.org/3/library/logging.html) module to log messages to the console and to a file.

### Default modes

#### Production JSON

FireFighter logs to stdout using a [JSON formatter][JSONFormatter] and to a file using a [JSON formatter][JSONFormatter].

The JSON formats adheres to DataDog's [JSON log format](https://docs.datadoghq.com/logs/log_collection/python/?tab=standard#json-format).

#### Development

In development mode, FireFighter logs to the console using a [Pretty formatter][PrettyFormatter]

### Further Configuration

You can configure the logging manually by editing the `LOGGING` Python setting, or by running your configuration code in your custom settings.

## Tracing

FireFighter use Datadog's [ddtrace](https://ddtrace.readthedocs.io/en/stable/index.html). Most configuration can be passed as environment variables.
