#!/usr/bin/env python3
"""
TRADOV - Multi-Agent Stock Trading System

Setup script for proper package installation and import resolution.

Usage:
    pip install -e .

Author: Tradov Team
"""

from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ''

def read_requirements(filename):
    requirements_file = this_directory / filename
    if requirements_file.exists():
        requirements = []
        for line in requirements_file.read_text(encoding='utf-8').strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-r'):
                requirements.append(line)
        return requirements
    return []

setup(
    name="tradov-trading-system",
    version="1.0.0",
    author="Tradov Team",
    description="Multi-Agent LLM-Powered Stock Trading System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mtalib/Tradov",
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
            'tradov=Tradov.TradovA_Core.TradovA01_Main:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
