import subprocess
from setuptools import setup, find_packages


def get_version_from_git():
    try:
        # Get the latest Git tag (e.g., v0.1.0)
        version = (
            subprocess.check_output(
                ["git", "describe", "--tags"], stderr=subprocess.STDOUT
            )
            .strip()
            .decode("utf-8")
        )
        return version
    except Exception:
        # Fallback to a default version if Git fails
        return "0.0.0"


def parse_requirements(file):
    with open(file) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


setup(
    name="wdg_micro_skeleton",
    version=get_version_from_git(),
    description="Django microservice project template",
    author="Rotana Phai",
    author_email="rotana.phai@wingbank.com.kh",
    url="https://bitbucket.org/wingdev/wdg_micro_skeleton",
    packages=find_packages(
        include=[
            "wdg_micro_skeleton",
            "wdg_micro_skeleton.apps",
            "wdg_micro_skeleton.configs",
            "wdg_micro_skeleton.requirements",
            "wdg_micro_skeleton.storages",
            "wdg_micro_skeleton.apps.*",
            "wdg_micro_skeleton.configs.*",
            "wdg_micro_skeleton.storages.*",
            "wdg_micro_skeleton.requirements.*",
        ]
    ),
    include_package_data=True,
    package_data={
        "wdg_micro_skeleton": [
            "apps/*",
            "configs/*",
            "requirements/*",
            "storages/*",
        ]
    },
    install_requires=parse_requirements("requirements/base.txt"),
    entry_points={
        "console_scripts": [
            "wdg_micro_skeleton=apps.core_service:main",
        ],
    },
)
