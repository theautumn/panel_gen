import os
from setuptools import setup, find_packages

def read(fname):
        return open(os.path.join(os.path.dirname(__file__), fname)).read()

requires = [
    'flask',
    'argparse',
    'logging',
    'requests',
    'tabulate',
    'subprocess'
    're'
    'curses'
    'numpy',
    'pathlib',
    'pycall',
    'asterisk-ami',
    'connexion',
    'marshmallow',
    'cherrypy',
]

setup(
    name='panel_gen',
    version='2.5',
    description='A call generator for the Connections Museum',
    long_description=read('README.md'),
    author='Sarah Autumn',
    author_email='sarah@connectionsmuseum.org',
    license='GPLv3',
    keywords='connections museum call simulator',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires
)
