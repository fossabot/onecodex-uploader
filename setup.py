#!/usr/bin/env python
from setuptools import setup

execfile('onecodex_uploader/version.py')

options = {
    'name': 'onecodex-uploader',
    'version': __version__  # noqa
}

setup(**options)
