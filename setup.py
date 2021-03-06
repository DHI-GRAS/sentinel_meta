from setuptools import setup, find_packages
import versioneer

setup(
    name='satmeta',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Satellite Meta Data Extraction',
    author='Jonas Solvsteen',
    author_email='josl@dhigroup.com',
    packages=find_packages(),
    install_requires=[
        'python-dateutil',
        'lxml',
        'shapely',
        'affine'
    ],
    extras_require={
        'test': [
            'pytest>=4.0',
            'codecov',
            'pytest-cov'
        ]})
