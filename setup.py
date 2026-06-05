from setuptools import setup, find_packages

setup(
    name="precios_uy",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "sqlalchemy>=2.0.0",
        "requests>=2.28.0",
        "beautifulsoup4>=4.10.0",
        "lxml>=4.9.0",
        "click>=8.1.0",
        "apscheduler>=3.10.0",
        "pydantic-settings>=2.0.0",
        "schedule>=1.2.0",
        "cloudscraper>=1.2.0",
    ],
    entry_points={
        "console_scripts": [
            "precios-uy=precios_uy.cli:main",
        ],
    },
)
