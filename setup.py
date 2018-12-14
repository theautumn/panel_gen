from setuptools import setup, find_packages

requires = [
    'flask',
    'argparse',
    'logging',
    'requests',
    'tabulate',
    'numpy',
    'pathlib',
    'pycall',
    'asterisk-ami',
    
]

setup(
    name='panel_gen',
    version='2.1',
    description='A call generator for the Connections Museum',
    author='Sarah Autumn',
    author_email='sarah@connectionsmuseum.org',
    keywords='connections museum call simulator',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires
)
