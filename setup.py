from setuptools import setup, find_packages

setup(
    name="ttt-tibia-tfs-transpiler",
    version="1.0.0",
    description="Universal script converter for The Forgotten Server (TFS)",
    author="TTT Project",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "ttt=ttt.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
