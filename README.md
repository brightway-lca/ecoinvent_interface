# ecoinvent_interface

[![PyPI](https://img.shields.io/pypi/v/ecoinvent_interface.svg)][pypi status]
[![Status](https://img.shields.io/pypi/status/ecoinvent_interface.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/ecoinvent_interface)][pypi status]
[![License](https://img.shields.io/pypi/l/ecoinvent_interface)][license]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

This is an **unofficial and unsupported** Python library to get ecoinvent data.

## Usage

### Authentication via `Settings` object

Authentication is done via the `Settings` object. Accessing ecoinvent requires supplying a username and password.

Note that you **must accept** the ecoinvent license and personal identifying information agreement on the website before using your user account via this library.

You can provide credentials in three ways:

* Manually, via arguments to the `Settings` object instantiation:

```python
from ecoinvent_interface import Settings
my_settings = Settings(username="bob", password="example")
```

* Via the `EI_PASSWORD` and `EI_USERNAME` environment variables

```bash
export EI_USERNAME=bob
export EI_PASSWORD=example
```

If your environment variable values have special characters, using single quotes should work, e.g. `export EI_PASSWORD='compl\!cat$d'`.

Followed by:

```python
from ecoinvent_interface import Settings
# Environment variables read automatically
my_settings = Settings()
```

* Or with the use of a [pydantic_settings secrets directory](https://docs.pydantic.dev/latest/usage/pydantic_settings/#secrets). The easiest way to create the correct files is via the utility function `permanent_setting`:

```python
from ecoinvent_interface import Settings, permanent_setting
permanent_setting("username", "bob")
permanent_setting("password", "example")
# Secrets files read automatically
my_settings = Settings()
```

Secrets files are stored in `ecoinvent_interface.storage.secrets_dir`.

For each value, manually set values always take precedence over environment variables, which in turn take precendence over secrets files.

### `EcoinventRelease` instantiation

To interact with the ecoinvent website, instantiate `EcoinventRelease`. You can specify your credentials manually when creating the class instance, or with the approaches outlined above.

```python
from ecoinvent_interface import EcoinventRelease
ei = EcoinventRelease()
```

All operations with `EcoinventRelease` require a valid login:

```python
ei.login()
```

You need to choose a valid version. You can list the version identifiers:

```python
ei.list_versions()
>>> ['3.9.1',
 '3.9',
 '3.8',
 '3.7.1',
 '3.7',
 ...]
```

### `EcoinventRelease` *extra* files

There are three kinds of files available: *reports*, *documentation* files, and what we call *extra* files. Let's see the *extra* files for version `'3.7.1'`:

```python
ei.list_extra_files('3.7.1')
>>>  {'ecoinvent 3.7.1_LCIA_implementation.7z': {
    'uuid': ...,
    'size': ...,
    'modified': datetime.datetime(2023, 4, 25, 0, 0)
  },
  ...
}
```

This returns a dictionary of filenames and metadata. We can download the 'ecoinvent 3.7.1_LCIA_implementation.7z' file; by default it will automatically be extracted.


```python
ei.get_extra(version='3.7.1', filename='ecoinvent 3.7.1_LCIA_implementation.7z')
>>> PosixPath('/Users/<your username>/Library/Application Support'
              '/EcoinventRelease/cache/ecoinvent 3.7.1_LCIA_implementation')
```

The default cache uses [platformdirs](https://platformdirs.readthedocs.io/en/latest/), and the directory location is OS-dependent. You can use a custom cache directory with by specifying `output_dir` when creating the `EcoinventRelease` class instance.

You can work with the cache when offline:

```python
cs = CachedStorage()
list(cs.catalogue)
>>> ['ecoinvent 3.7.1_LCIA_implementation.7z']
cs.catalogue['ecoinvent 3.7.1_LCIA_implementation.7z']
>>> {
  'path': '/Users/<your username>/Library/Application Support/'
          'EcoinventRelease/cache/ecoinvent 3.7.1_LCIA_implementation',
  'extracted': True,
  'created': '2023-09-03T20:23:57.186519'
}
```

### `EcoinventRelease` *release* files

Most of you are here for the *release* files. We first need to figure what system models are available for our desired version:

```python
ei.list_system_models('3.7.1')
>>> ['cutoff', 'consequential', 'apos']
```

The ecoinvent API uses a short and long form of the system model names; you can get the longer names by passing `translate=False`. You can use either form in all `EcoinventRelease` methods.

```python
ei.list_system_models('3.7.1', translate=False)
>>> [
  'Allocation cut-off by classification',
  'Substitution, consequential, long-term',
  'Allocation at the Point of Substitution'
]
```

Release files have one more complication - the release type. You need to choose from one of:

* `ecospold`: The single-output unit process files in ecospold2 XML format
* `matrix`: The so-called "universaml matrix export"
* `lci`: LCI data in ecospold2 XML format
* `lcia`: LCIA data in ecospold2 XML format
* `cumulative_lci`: LCI data in Excel
* `cumulative_lcia`: LCIA data in Excel

See the ecoinvent website for information on what these values mean. We need to pass in an option for the `ReleaseType` enum when asking for a release file. We use the enum to guess the filenames.

```python
ei.get_release(version='3.7.1', system_model='apos', release_type=ReleaseType.matrix)
>>> PosixPath('/Users/<your username>/Library/Application Support/'
              'EcoinventRelease/cache/universal_matrix_export_3.7.1_apos')
```

### `EcoinventRelease` *reports*

Reports require a login but not a version number:

```python
ei.list_report_files()
>>> {'Allocation, cut-off, EN15804_documentation.pdf': {
    'uuid': ...,
    'size': ...,
    'modified': datetime.datetime(2021, 10, 1, 0, 0),
    'description': 'This document provides a documentation on the calculation of the indicators in the “Allocation, cut-off, EN15804” system model.'
  },
}
```

Downloading follows the same pattern as before:

```python
ei.get_report('Allocation, cut-off, EN15804_documentation.pdf')
>>> PosixPath('/Users/<your username>/Library/Application Support/EcoinventRelease/cache/Allocation, cut-off, EN15804_documentation.pdf')
```

Zip and 7z files are extracted by default.

## Relationship to EIDL

This library initially started as a fork of [EIDL](https://github.com/haasad/EcoInventDownLoader), the ecoinvent downloader. As of version 2.0, it has been completely rewritten. Currently only the authentication code comes from `EIDL`.

Differences with `EIDL`:

* Designed to be a lower-level infrastructure library. All user and web browser interaction was removed.
* Username and password can be specified using [pydantic_settings](https://docs.pydantic.dev/latest/usage/pydantic_settings/).
* Can download all release files, plus reports and "extra" files.
* Will autocorrect filenames when possible for ecoinvent inconsistencies.
* Uses a more robust caching and cache validation strategy.
* More reasonable token refresh strategy.
* No HTML or filename string hacks.
* Streaming downloads.
* Descriptive logging and error messages.
* No shortcuts for Brightway or other LCA software.
* Custom library headers are set to allow users of this library to be identified. No user information is transmitted.

## Contributing

Contributions are very welcome, but please note the following:

* This library consumes and unpublished an under development API
* Extensions of the current API to get process LCI or LCIA data or LCIA scores won't be included
* Brightway-specific code won't be included

To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [MIT license][license],
_ecoinvent_interface_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.


<!-- github-only -->

[command-line reference]: https://ecoinvent_interface.readthedocs.io/en/latest/usage.html
[license]: https://github.com/brightway-lca/ecoinvent_interface/blob/main/LICENSE
[contributor guide]: https://github.com/brightway-lca/ecoinvent_interface/blob/main/CONTRIBUTING.md
