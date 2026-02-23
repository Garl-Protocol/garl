from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="garl",
    version="1.0.2",
    author="GARL Protocol",
    author_email="hello@garl.ai",
    description="GARL Protocol Python SDK — Universal Trust Standard for AI Agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://garl.ai",
    project_urls={
        "Documentation": "https://garl.ai/docs",
        "API Reference": "https://api.garl.ai/docs",
        "Source": "https://github.com/garl-protocol/garl",
    },
    py_modules=["garl"],
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.24.0",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="garl trust reputation ai agent a2a did ecdsa mcp",
)
