"""Minimal setup.py for editable install support."""
from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="reddit-research",
    version="1.0.0",
    py_modules=["run"],
    packages=find_packages(include=["scripts*"]),
    package_data={
        "": ["config/*.txt", "config/*.json", "prompts/*.md", "agents/*.md"],
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "reddit-research=run:main",
        ],
    },
    install_requires=[
        "markdown2>=2.4",
        "weasyprint>=60.0",
    ],
    python_requires=">=3.9",
)
