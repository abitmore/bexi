#!/usr/bin/env python

from setuptools import setup, find_packages
import sys
import os

assert sys.version_info[0] == 3, "We require Python > 3"

with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'VERSION')) as version_file:
    version = version_file.read().strip()

setup(
    name='bexi',
    version=version,
    description=(
        'BitShares Exchange Integration (BEXI).'
        'A toolkit that allows to deal with deposits and withdrawals on'
        'the BitShares Blockchain.'
    ),
    long_description=open('README.rst').read(),
    download_url='https://github.com/blockchainbv/bexi/tarball/' + version,
    author='Blockchain BV',
    author_email='info@BlockchainBV.com',
    maintainer='Blockchain Projects BV',
    maintainer_email='info@BlockchainProjectsBV.com',
    url='http://blockchainprojectsbv.com',
    keywords=['bitshares'],
    packages=find_packages(),
    classifiers=[
        'License :: OSI Approved :: LGPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Development Status :: Beta',
        'Intended Audience :: Developers',
    ],
    entry_points={
        'console_scripts': [
            'bexi = cli:main'
        ],
    },
    install_requires=open('requirements.txt').read().split(),
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    include_package_data=True,
)
