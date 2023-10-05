#!/usr/bin/python3

# Publish
#   ./sh/clean.sh && python3 ./setup.py bdist_wheel
#   python3 -m twine upload dist/*

import os
from setuptools import setup

def readConfig(fname):
    cfg = {}
    with open(fname) as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().replace("\t", " ").split(" ")
            k = parts.pop(0).strip()
            if '#' != k[0]:
                cfg[k] = " ".join(parts).strip()
    return cfg

here = os.path.abspath(os.path.dirname(__file__))

# Read in the config
cfg = readConfig(os.path.join(here, 'memcom', 'PROJECT.txt'))

# Read in the README
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
if not long_description:
    long_description = cfg['description']

setup(
    name=cfg['name'],
    version=cfg['version'],
    description=cfg['description'],
    url=cfg['url'],
    author=cfg['author'],
    author_email=cfg['email'],
    license=cfg['license'],
    packages=[cfg['name']],
    include_package_data = True,
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
            'av',
            'Pillow',
            'propertybag',
            'sparen'
        ],
    dependency_links=[
        ]
)
