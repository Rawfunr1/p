#!/usr/bin/env python3
"""Setup script for Floorplan2DXF converter."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

# Read requirements
requirements_file = Path(__file__).parent / 'requirements.txt'
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text(encoding='utf-8').strip().split('\n')
    requirements = [r.strip() for r in requirements if r.strip() and not r.startswith('#')]

setup(
    name='floorplan2dxf',
    version='2.0.0',
    description='Convert floor plan images to DXF and 3D formats using deep learning',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Refactored Version',
    python_requires='>=3.8',
    packages=find_packages(exclude=['tests', 'docs']),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'floorplan2dxf=floorplan_main:main',
            'floorplan-app=app:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Image Recognition',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    keywords='floor-plan dxf 3d-modeling computer-vision deep-learning',
    project_urls={
        'Source': 'https://github.com/Rawfunr1/p',
        'Bug Reports': 'https://github.com/Rawfunr1/p/issues',
    },
)
