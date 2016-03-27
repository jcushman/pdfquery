# -*- coding: utf-8 -*-
import sys
from setuptools import setup, find_packages

# set up tests
if sys.version_info[:2] < (2, 7):
    test_suite = 'unittest2.collector'
else:
    test_suite = 'tests'

# Work around a traceback on Python < 2.7.4 and < 3.3.1
# http://bugs.python.org/issue15881#msg170215
try:
    import multiprocessing  # noqa: unused
except ImportError:
    pass

setup(
    name='pdfquery',
    version='0.4.3',
    author=u'Jack Cushman',
    author_email='jcushman@gmail.com',
    packages=find_packages(),
    url='https://github.com/jcushman/pdfquery',
    license='MIT',
    description='Concise and friendly PDF scraper using JQuery or XPath selectors.',
    keywords='',
    long_description=open('README.rst').read(),
    install_requires = open('requirements_py3.txt').read() if sys.version_info >= (3, 0) else open('requirements_py2.txt').read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Text Processing",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        ],

    test_suite=test_suite,
)
