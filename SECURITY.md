# Security Policy

## Supported Versions

PVNM has not had its first public versioned release yet. Until that release, security fixes are handled on the `main` branch.

| Version | Supported |
| --- | --- |
| Unreleased / `main` | Yes |

After the first public release, this table will be updated with supported version ranges.

## Reporting a Vulnerability

Please do not report sensitive issues in a public Issue.

Examples of sensitive issues include:

- Leaked signing keys, tokens, or API keys
- Private assets accidentally included in the public repository or generated releases
- Arbitrary code execution
- Build or release tampering
- Export behavior that can expose private local files

If GitHub Security Advisories are enabled for the repository, use the repository's Security Advisory flow. If they are not available, contact the maintainer privately through GitHub or another published private contact route.

Public Issues and Pull Requests are fine for normal bugs, documentation mistakes, and non-sensitive feature requests.

## Secrets

Do not commit files or values such as:

- GitHub tokens
- Android keystores
- `pvnm-release-signing.properties`
- `*.jks`
- `*.keystore`
- API keys
- Private assets
- Settings files containing personal local paths

If a secret is committed or published by mistake, revoke or rotate the secret immediately. Then decide whether repository history or release assets also need to be cleaned.
