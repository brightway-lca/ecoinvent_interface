### 2.4.1 (2023-12-07)

* Fix missing f-string in error message

## 2.4 (2023-11-08)

* Added `get_excel_lcia_file_for_version` utility function

## 2.3 (2023-11-07)

* Switch to internal, BSD-licensed Levenshtein code
* Fix not using cache for release archives

## 2.2.1 (2023-10-23)

* Remove some CI debugging code

## 2.2 (2023-10-23)

* Add default fixing of ecoinvent release `majorRelease` and `minorRelease` values for unit process and metadata XML files
* Specification of UTF-8 text encoding on all file calls

### 2.1.1 (2023-10-17)

* Minor packaging fixes

## 2.1 (2023-10-17)

* Change packaging to `pyproject.toml`

### 2.0.1 (2023-10-11)

Fix a Windows encoding problem.

# 2.0 (2023-10-11)

Complete rewrite. This is now an independent library with a completely new API.

All Brightway functionality is removed.

# 1.0

Fork of https://github.com/haasad/EcoInventDownLoader (EIDL) with storage of secrets and a few additional methods.
