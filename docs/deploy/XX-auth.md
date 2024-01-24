# Authentication and authorization

## Foreword

FireFighter was developed with the assumption that it would be deployed in a private network, and that the only users would be trusted users. As such, we have not invested a lot of time into making the authentication and authorization system robust.

## Authentication

FireFighter uses Django's built-in authentication system.

FireFighter is configured with the following authentication backends:

- "oauth2_authcodeflow.auth.AuthenticationBackend,
- "django.contrib.auth.backends.ModelBackend"

Most routes will redirect to the OIDC provider if the user is not authenticated.

`/admin/` route allows for a back-up password authentication.

## Authorization

FireFighter uses Django's built-in group and permission system.

**Most actions have no authorization checks.**
