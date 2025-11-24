from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in advanced_attendance/__init__.py
from advanced_attendance import __version__ as version

setup(
    name="advanced_attendance",
    version=version,
    description="Advanced ERPNext Attendance & Roster System with geofencing, mobile clock-in, and biometric integration",
    author="Winco Group",
    author_email="admin@winco-group.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
