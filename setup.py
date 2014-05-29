# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='pdfquery',
    version='0.2.4',
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
)
