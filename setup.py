from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='flatfox-api',

    version='0.1.0',

    description='Flatfox api helper',
    long_description=long_description,

    url='https://github.com/flatfox/flatfox-api',

    author='flatfox AG',
    author_email='admin@flatfox.ch',
    license='internal use only',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        # 'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2.7',
    ],

    keywords='flatfox api',
    packages=find_packages(),
    provides=['flatfox_api'],
    install_requires=['requests', 'six'],
)
