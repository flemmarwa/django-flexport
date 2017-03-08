# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

install_requires = [
    'django>=1.7.0',
    'pandas>=0.19.2',
    'xlwt>=0.7.5',
    'XlsxWriter>=0.9.6'
]

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

version = __import__('django').get_version()

setup(
    name = "django-flexport",
    version = version,
    url = 'https://github.com/flemmarwa/django-flexport',
    license = 'BSD',
    description = "Flexible exporter for Django admin",
    long_description = read('README.rst'),
    author = 'Alessandro Regolini',
    author_email = 'alereg@gmail.com',
    packages = find_packages(),
    install_requires = install_requires,
    classifiers = [
        'Development Status :: 1 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        ],
    include_package_data=True,
    zip_safe = False
)
