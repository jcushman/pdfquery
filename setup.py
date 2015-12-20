# -*- coding: utf-8 -*-
import sys
from setuptools import setup, find_packages

# set up tests
if sys.version_info[:2] < (2, 7):
    tests_require = ['unittest2']
    test_suite = 'unittest2.collector'
else:
    tests_require = []
    test_suite = 'tests'

# Work around a traceback on Python < 2.7.4 and < 3.3.1
# http://bugs.python.org/issue15881#msg170215
try:
    import multiprocessing  # noqa: unused
except ImportError:
    pass

setup(
    name='pdfquery',
    version='0.3.1',
    author=u'Jack Cushman',
    author_email='jcushman@gmail.com',
    packages=find_packages(),
    url='https://github.com/jcushman/pdfquery',
    license='MIT',
    description='Concise and friendly PDF scraper using JQuery or XPath selectors.',
    keywords='',
    long_description=open('README.rst').read(),
    install_requires = open('requirements.txt').read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Text Processing",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        ],

    tests_require=tests_require,
    test_suite=test_suite,
)
