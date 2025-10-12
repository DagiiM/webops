"""Setup script for webops-cli."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="webops-cli",
    version="0.1.0",
    author="WebOps Team",
    author_email="support@webops.dev",
    description="Command-line interface for WebOps hosting platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/webops",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1.0",
        "requests>=2.31.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "webops=webops_cli.cli:main",
        ],
    },
)
