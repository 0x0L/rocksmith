from setuptools import setup


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='rocksmith',
    version='0.1',
    description='Rocksmith 2014 tools',
    long_description=readme(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='guitar rocksmith',
    url='http://github.com/0x0L/rocksmith',
    author='0x0L',
    author_email='0x0L@github.com',
    license='MIT',
    packages=['rocksmith'],
    entry_points={
        'console_scripts': ['pyrocksmith=rocksmith.command_line:main'],
    },
    install_requires=['pycryptodome', 'construct'],
    include_package_data=True,
    zip_safe=False
)
