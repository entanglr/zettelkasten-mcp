from setuptools import find_packages, setup
setup(
    name="zettelkasten_mcp",
    version="1.2.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    include_package_data=True,
    install_requires=[
        "mcp[cli]>=1.2.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
        "python-frontmatter>=1.0.0",
        "markdown>=3.4.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zettelkasten-mcp=zettelkasten_mcp.main:main",
        ],
    },
)
