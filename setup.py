from setuptools import setup, find_packages

setup(
    name="asyncwebostv",
    version="0.1.0",
    author="AsyncWebOSTV Team",
    author_email="your-email@example.com",
    description="Asynchronous client library for LG WebOS TVs",
    long_description=open("async_migration_spec.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/asyncwebostv",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
    ],
    python_requires=">=3.7",
    install_requires=[
        "aiohttp>=3.8.0",
        "websockets>=10.0",
        "aiofiles>=0.8.0",
        "aiohttp-sse-client>=0.2.0",
        "aiohttp-socks>=0.7.0",
    ],
) 