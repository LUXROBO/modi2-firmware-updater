from os import path

from setuptools import setup, find_packages


def get_readme():
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, 'README.md'), encoding='utf-8') as readme_file:
        readme = readme_file.read()
        return readme

def get_requirements():
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, 'requirements.txt'), encoding='utf-8') as \
        requirements_file:
        requirements = requirements_file.read().splitlines()
        return requirements


setup(
    name='modi2-multi-upploader',
    version='0.0.0',
    author='LUXROBO',
    author_email='tech@luxrobo.com',
    description='A GUI Form of MODI Firmware Updater utilizing PyMODI as its backend.',
    long_description=get_readme(),
    long_description_content_type='text/markdown',
    license='MIT',
    install_requires=get_requirements(),
    url='https://git.luxrobo.net/modi2-tools/modi2-multi-uploader',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ],
)

