from setuptools import setup

setup(
    name="rocksmith",
    version="0.2",
    description="Rocksmith 2014 tools",
    classifiers=[
        "Development Status :: 3 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="guitar rocksmith",
    url="http://github.com/0x0L/rocksmith",
    author="0x0L",
    author_email="0x0L@github.com",
    license="MIT",
    packages=["rocksmith"],
    entry_points={"console_scripts": ["pyrocksmith=rocksmith.main:main"]},
    install_requires=["construct", "cryptography"],
    include_package_data=True,
    zip_safe=False,
)
