#!/usr/bin/env python

import bexi

from setuptools import setup, find_packages
import sys

assert sys.version_info[0] == 3, "We require Python > 3"

setup(
    name='bexi',
    version=bexi.__VERSION__,
    description=(
        'BitShares Exchange Integration (BEXI).'
        'A toolkit that allows to deal with deposits and withdrawals on'
        'the BitShares Blockchain.'
    ),
    long_description=open('README.rst').read(),
    download_url='https://github.com/blockchainbv/bexi/tarball/' + __VERSION__,
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
