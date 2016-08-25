#!/usr/bin/env python
from setuptools import setup

with open('onecodex_uploader/version.py') as import_file:
    exec(import_file.read())


options = {
    'name': 'onecodex-uploader',
    'version': __version__  # noqa
}

setup(**options)
