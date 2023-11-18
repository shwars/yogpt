#!/usr/bin/env python

import setuptools

with open('README.md') as readme_file:
    readme = readme_file.read()

setuptools.setup(
    name='yogpt',
    packages=setuptools.find_namespace_packages('.'),
    version='0.0.1',
    install_requires=['requests','langchain'],
    description='Command-line interface for GPT-like LLMs',
    author='Dmitri Soshnikov',
    author_email='dmitri@soshnikov.com',
    url='https://github.com/shwars/yogpt',
    long_description=readme,
    long_description_content_type='text/markdown; charset=UTF-8',
    license='MIT license',
    entry_points = {
        'console_scripts': ['yogpt=yogpt.cli:main'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
#        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
#        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
#   test_suite = 'tests'
)