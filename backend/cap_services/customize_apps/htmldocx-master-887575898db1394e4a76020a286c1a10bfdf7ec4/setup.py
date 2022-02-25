import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="htmldocx",
    version="0.0.8",
    author="pqzx",
    author_email="jc3664@gmail.com",
    description="Convert html to docx",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pqzx/h2d",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "python-docx >= 0.8.9",
        "beautifulsoup4 >= 4.7.1",
        "webcolors >= 1.11.1"
    ]
)