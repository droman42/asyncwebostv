from setuptools import setup, find_packages

# This setup.py file exists for compatibility with legacy build systems
# All configuration is done in pyproject.toml
setup(
    name="asyncwebostv",
    version="0.3.0",
    packages=find_packages(),
    install_requires=[
        "websockets>=15.0.1",
        "aiohttp>=3.8.0",
        "zeroconf>=0.36.0",
    ],
    author="Denis Papathanasiou",
    author_email="denis@papathanasiou.org",
    description="Asynchronous package for controlling WebOS-based LG TV",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/papathanasiou/asyncwebostv",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
) 