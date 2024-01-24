# Internationalization, Localization and timezones (i18n, l10n and TZ)

## Internationalization

We plan to support Django's [internationalization](https://docs.djangoproject.com/en/4.2/topics/i18n/), but it is not used or tested, and currently disabled.

**Most of the code is in English, and we don't have any translation files.**

> If you are interested in translating FireFighter, please open an issue.

## Localization

We support Django's [localization](https://docs.djangoproject.com/en/4.2/topics/i18n/), but it is only used with a single locale.

We currently override some date formats to use an international format (YYYY-MM-DD, 24 hours time) in the configuration and  [][firefighter.firefighter.formats]

## Timezones

We currently only support deploying with a single timezone.

Use Django's [timezone support](https://docs.djangoproject.com/en/4.2/topics/i18n/timezones/) to configure the timezone.
