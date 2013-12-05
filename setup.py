#!/usr/bin/env python
import os

from setuptools import setup

__doc__ = """
    Make it easy to allow users to import CSV files using the django admin site.
"""

def read(fname):
    fpath = os.path.join(os.path.dirname(__file__), fname)
    with open(fpath, 'r') as f:
        return f.read()

setup(
    name="django-importcsvadmin",
    version="0.0.1pre",
    author="Fusionbox, Inc.",
    author_email="programmers@fusionbox.com",

    license="BSD",
    description=__doc__,
    long_description=read('README.rst') + '\n\n' + read('CHANGELOG.rst'),

    keywords='django admin interface csv import',
    packages=['importcsvadmin', ],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
    ]
)
