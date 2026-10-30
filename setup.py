import os

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rocksmith",
    version="0.3",
    description="Rocksmith 2014 tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment",
    ],
    keywords="guitar rocksmith psarc sng",
    url="http://github.com/0x0L/rocksmith",
    author="0x0L",
    author_email="0x0L@github.com",
    license="MIT",
    packages=["rocksmith"],
    entry_points={"console_scripts": ["pyrocksmith=rocksmith.main:main"]},
    install_requires=["construct>=2.10,<3", "cryptography"],
    extras_require={"test": ["pytest"]},
    include_package_data=True,
    zip_safe=False,
)
