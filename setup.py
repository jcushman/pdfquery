# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='pdfquery',
    version='0.1.0',
    author=u'Jack Cushman',
    author_email='jcushman@gmail.com',
    packages=find_packages(),
    url='https://github.com/jcushman/pdfquery',
    license='MIT',
    description='A fast and friendly PDF scraping library using JQuery or XPath selectors.',
    keywords='',
    long_description=open('README.rst').read(),
    install_requires = ['pdfminer', 'pyquery', 'lxml'],
)