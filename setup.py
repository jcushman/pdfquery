import sys

from setuptools import find_packages, setup

TESTS_REQUIRE = [
    'pytest',
    'tox',
    'isort',
    'freezegun',
    'pre-commit'
]

setup(
    name='pdfquery',
    version='0.5.1.dev0',
    author=u'Jack Cushman',
    author_email='jcushman@gmail.com',
    packages=find_packages(),
    url='https://github.com/jcushman/pdfquery',
    license='MIT',
    description='Concise and friendly PDF scraper using JQuery or XPath selectors.',
    keywords='',
    long_description=open('README.rst').read(),
    install_requires=open('requirements.txt').read(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Text Processing",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.9",
        ],
    extras_require=dict(
        test=TESTS_REQUIRE,
        pep8=['flake8'],
        coverage=['pytest-cov'],
        docs=['sphinx'],
        release=['zest.releaser'],
    ),
    test_suite='tests',
)
