#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Setup script for proper package installation and import resolution.
This resolves "No module named Spyder" import errors.

Usage:
    pip install -e .

Author: SPYDER Team
Date Created: 2025-01-04
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ''

# Read requirements
def read_requirements(filename):
    """Read requirements from file, filtering out comments and empty lines."""
    requirements_file = this_directory / filename
    if requirements_file.exists():
        requirements = []
        for line in requirements_file.read_text(encoding='utf-8').strip().split('\n'):
            line = line.strip()
            # Skip empty lines, comments, and -r includes
            if line and not line.startswith('#') and not line.startswith('-r'):
                requirements.append(line)
        return requirements
    return []

setup(
    name="spyder-trading-system",
    version="1.0.0",
    author="SPYDER Team",
    author_email="team@spyder-trading.com",
    description="Automated SPY Options Trading System with AI-powered strategies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/Spyder",
    packages=find_packages(exclude=['tests*', 'docs*', 'scripts*']),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.12",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        'dev': read_requirements("requirements-dev.txt"),
        'gui': read_requirements("requirements-gui.txt"),
        'trading': read_requirements("requirements-trading.txt"),
        'analysis': read_requirements("requirements-analysis.txt"),
        'ai': read_requirements("requirements-ai.txt"),
    },
    entry_points={
        'console_scripts': [
            'spyder=Spyder.SpyderA_Core.SpyderA01_Main:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
