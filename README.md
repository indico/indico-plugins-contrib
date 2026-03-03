# Indico Third-Party Plugins [![CI Status][ci-badge]][ci-link] [![License][license-badge]][license-link]

This repository contains third-party plugins for [Indico][indico].

These plugins are licensed under the MIT license.

Neither the Indico team nor CERN give you any guarantees that plugins in this repo are bug-free,
working as expected or meet the quality standards of the Indico project itself.


## Versioning

Plugins in this repo MUST follow the Indico plugin versioning schema, which means that the first
two version number digits MUST match the minimum Indico version they are compatible with.

So for example, in early 2026 this is Indico v3.3, so the initial release version of a plugin
should be `3.3` as well. If you make use of the version number within your plugin, bump the third
segment whenever appropriate, e.g. `3.3.1`. It is recommended to also keep a changelog in your
plugin's README.md for each version. If you do not use PyPI to publish your plugin and do not care
about versioning and a changelog, you can also stick with `3.3-dev` and benefit of the version
suffix that the build scripts (and CI build job) can automatically append (`--add-version-suffix`),
which results in the version number of each build being higher than that of an older build.


## Compatibility

When making changes in the Indico core that affect a plugin in this repo, the Indico team will
usually add a commit to adapt any plugin in this repository, and - if the change is not compatible
with older Indico versions - bump the required Indico version in `pyproject.toml` as well. This
generally includes pre-releases of that version, e.g. `indico>=3.3.10.dev0` if the plugin requires
something that was added in Indico v3.3.10.

When opening a pull request that adds or updates a plugin which also requires changes to the Indico
core (such as adding a new signal), then you need to open a separate PR against the core Indico repo
and reference it in your PR - that way the CI tests of the plugin will use your PR's branch instead
of `master`.


## Adding a new plugin

Follow the structure that existing plugins in [indico-plugins] have. In particular, your
`pyproject.toml` file should be copied from one of these plugins and just be adjusted to include
the data related to your own plugin (ie the technical metadata and author information). Usually the
easiest is copying a complete plugin to have all the boilerplate. Also, add the plugin to the
`plugin-name` dropdown in the `workflow_dispatch` inputs in both `build.yml` and `pypi.yml`, and
to the build matrix in `ci.yml`.

Also add a `.header.yaml` in your plugin to benefit from file copyright headers mentioning your
name and when you created the plugin:

```yaml
owner: Sneaky Cat
start_year: 2026
```

If you want to benefit from PyPI releases done via GitHub, then please reach out to us (via an issue
unless you have access to other channels) and setup a [Trusted Publisher via PyPI][pypi-publish]
("Add a new pending publisher") for the plugin's name (which would be `indico-plugin-<fancy-stuff>`
if the Python package is `indico_fancy_stuff`) with the following data:

- Owner: `indico`
- Repository name: `indico-plugins-contrib`
- Workflow: `pypi.yml`
- Environment name: `publish`

There is currently no automation for creating tags or creating releases. Just ping us and we'll take
care of it.


## Requirements for plugins

As mentioned above, plugins here do not need to meet our strict quality standards (but you make us
happy by meeting them anyway). However, we do have some basic requirements:

- Plugins MUST be licensed under the MIT license, and MUST NOT contain any minified or otherwise
  obfuscated or compiled code.
- CI and linters MUST pass, and a plugin SHOULD NOT disable linting rules without a good reason
- Plugins SHOULD have tests, and these test MUST be run in the CI (by adding them to the build
  matrix in `ci.yml`)
- Plugins MUST work with `CSP_ENABLED = True` in `indico.conf`
- Plugins MUST NOT be "AI slop" or "vibe-coded" - if you use LLMs when developing your plugin, you
  MUST understand their output and also disclose that AI was used and how it was used in your pull
  request. You MUST NOT blindly pass on any feedback you receive on PRs into your LLM: If we give
  feedback, we expect a human to read, understand and act on it. We do not want to write prompts
  for your LLM.
- Plugins MUST provide some general usefulness for others; if it provides zero benefit for
  anyone but the author (e.g. because it integrates w/ a company-specific API), then it should
  reside in your own repository
- Plugins MUST have a `README.md` file that describe what the plugin does and SHOULD contain a
  changelog
- Plugins MUST be a good "cultural fit" in the Indico ecosystem. For example, anything related to
  core Indico functionality is usually fine. Ask us if you are not sure.
- Plugin authors SHOULD monitor the issue tracker for issues related to their plugin, and be
  reachable under an email address published in the README and/or the `pyproject.toml` author
  metadata
- Plugins MAY integrate with cloud services that require a subscription to use; in this case the
  necessary credentials MUST be configurable via plugin settings, unless there is a strong argument
  for an alternative (e.g. a configuration file specific to the ecosystem such as `~/.aws/...` when
  interacting with AWS services)
- Authors of plugins that interact with cloud services SHOULD consider whether it makes sense to let
  event managers provide their own credentials. In that case they SHOULD allow admins to configure a
  global API which MUST not be visible to event organizers (who are usually not admins), and the
  event-level configuration form SHOULD have an option to opt-out from using the global credentials
  and provide custom ones. If not global credentials are configure, the this form MUST require
  credentials to be entered in order to enable the plugin's functionality. You can have a look
  at the Stripe plugin to get an example on how this could be done in case of a payment plugin.
- Plugins that interact with cloud services SHOULD mention in their README how to get free (test)
  credentials in order to test the functionality of the plugin, or at least link to the website of
  the cloud service they integrate with.


## Note

In applying the MIT license, CERN does not waive the privileges and immunities granted to it by
virtue of its status as an Intergovernmental Organization or submit itself to any jurisdiction.


[ci-badge]: https://github.com/indico/indico-plugins-contrib/actions/workflows/ci.yml/badge.svg
[ci-link]: https://github.com/indico/indico-plugins-contrib/actions/workflows/ci.yml
[license-link]: https://github.com/indico/indico-plugins-contrib/blob/master/LICENSE
[license-badge]: https://img.shields.io/github/license/indico/indico-plugins-contrib.svg
[indico]: https://github.com/indico/indico
[indico-plugins]: https://github.com/indico/indico-plugins
[pypi-publish]: https://pypi.org/manage/account/publishing/
