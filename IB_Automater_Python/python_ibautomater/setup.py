#!/usr/bin/env python3
"""
Python IBAutomater - Interactive Brokers Gateway Automation Tool
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="python-ibautomater",
    version="1.0.0",
    author="Python IBAutomater Team",
    author_email="contact@example.com",
    description="Automation tool for Interactive Brokers Gateway",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/python-ibautomater",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pyautogui>=0.9.54",
        "opencv-python>=4.5.0",
        "pillow>=8.0.0",
        "psutil>=5.8.0",
        "numpy>=1.20.0",
        "pytesseract>=0.3.8",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
    },
    entry_points={
        "console_scripts": [
            "ibautomater=ibautomater.cli:main",
        ],
    },
)

