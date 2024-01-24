# Custom settings

You can specify a custom settings module by setting the `FF_ADDITIONAL_SETTINGS_MODULE` environment variable.

It will load after all default settings have been loaded, so you can override any setting.

You can also use this to run any custom code you want to run when FireFighter starts up.

> The module must be importable from the Python path.
> You must not include the `.py` extension.

!!! info
    While most things can be configured with environment variables or through the BackOffice, some settings can only be configured by editing the settings module.

## Writing your custom settings module

In your custom settings module, you can import the `firefighter.settings.settings_utils`.

If importing other things, beware of circular imports and imports made before Django has been initialized.

Do not try to load `django.conf.settings` or `firefighter.settings` as they will not be loaded yet.

## Advanced: override built-in settings

You can also change `DJANGO_SETTINGS_MODULE` to point to your own settings module.

We recommend you load `firefighter.settings` in your settings module, and override the settings you want to change.

!!! warning
    Modifying Django settings or third-party settings may break FireFighter.
