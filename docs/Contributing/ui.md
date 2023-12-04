# UI

## Web UI

## Javascript Graceful degradation

We use [htmx](https://htmx.org/) to build the web UI. It is a small JS library that allows you to access AJAXdirectly in HTML, using attributes like `hx-get`, `hx-post`, `hx-swap`, `hx-trigger`, etc.

It allows, in conjonction with [Alpine.js](https://alpinejs.dev/) to have a more dynamic UI, without having to write a lot of JS code.

The UI should be usable without JS, and should be accessible. If you need to use JS, make sure it is accessible.

> The goal is to be usable without JS, even if the experience is really degraded.

## Tailwind CSS

Firefighter uses [Tailwind CSS](https://tailwindcss.com/) for styling. It is a utility-first CSS framework, which means it provides a set of utility classes that can be used to build your UI. It is highly customizable and easy to use.

We use [Tailwind UI](https://tailwindui.com/) and [DaisyUI](https://daisyui.com/) to build the UI.

### Icons

FireFighter web uses icons from [HeroIcons](https://heroicons.com/), solid style. For consistency, use them as much as possible.

### Color-scheme

FireFighter web supports both light and dark theme, following the browser CSS feature `prefers-colors-scheme`. Make sure everything is legible and good-looking in both themes.
