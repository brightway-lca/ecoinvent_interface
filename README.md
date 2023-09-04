# ecoinvent_interface

[![PyPI](https://img.shields.io/pypi/v/ecoinvent_interface.svg)][pypi status]
[![Status](https://img.shields.io/pypi/status/ecoinvent_interface.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/ecoinvent_interface)][pypi status]
[![License](https://img.shields.io/pypi/l/ecoinvent_interface)][license]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

This is an **unofficial and unsupported** Python library to get ecoinvent data.

## Usage

### Authentication

Note that you **must accept** the ecoinvent license via the website before using your user account via this library.

TBD: Environment variables

TBD: `.env` file and creation utility

### `EcoinventInterface` instantiation

To interact with the ecoinvent website, instantiate `EcoinventInterface`. You can specify your credentials manually when creating the class instance, or with the approaches outlined above.

```python
from ecoinvent_interface import EcoinventInterface, ReleaseType, CachedStorage
ei = EcoinventInterface()
```

All operations with `EcoinventInterface` require a valid login:

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

### `EcoinventInterface` *extra* files

There are two kinds of files available: *release* files, and what we call *extra* files. Let's see the *extra* files for version `'3.7.1'`:

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
              '/EcoinventInterface/cache/ecoinvent 3.7.1_LCIA_implementation')
```

The default cache uses [platformdirs](https://platformdirs.readthedocs.io/en/latest/), and the directory location is OS-dependent. You can use a custom cache directory with by specifying `output_dir` when creating the `EcoinventInterface` class instance.

You can work with the cache when offline:

```python
cs = CachedStorage()
list(cs.catalogue)
>>> ['ecoinvent 3.7.1_LCIA_implementation.7z']
cs.catalogue['ecoinvent 3.7.1_LCIA_implementation.7z']
>>> {
  'path': '/Users/<your username>/Library/Application Support/'
          'EcoinventInterface/cache/ecoinvent 3.7.1_LCIA_implementation',
  'extracted': True,
  'created': '2023-09-03T20:23:57.186519'
}
```

### `EcoinventInterface` *release* files

Most of you are here for the *release* files. We first need to figure what system models are available for our desired version:

```python
ei.list_system_models('3.7.1')
>>> ['cutoff', 'consequential', 'apos']
```

The ecoinvent API uses a short and long form of the system model names; you can get the longer names by passing `translate=False`. You can use either form in all `EcoinventInterface` methods.

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
              'EcoinventInterface/cache/universal_matrix_export_3.7.1_apos')
```

## Relationship to EIDL

This library initially started as a fork of [EIDL](https://github.com/haasad/EcoInventDownLoader), the ecoinvent downloader. As of version 2.0, it has been completely rewritten. Currently only the authentication code comes from `EIDL`.

Differences with `EIDL`:

* Designed to be a lower-level infrastructure library. All user and web browser interaction was removed.
* Username and password can be specified using [pydantic_settings](https://docs.pydantic.dev/latest/usage/pydantic_settings/).
* Can download all release and extra file types.
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

* This library consumes an unpublished an under development API
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
