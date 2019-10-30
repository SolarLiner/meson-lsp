from distutils.core import setup

setup(
    name='mlsp',
    version='0.1',
    packages=['mlsp'],
    install_requires=[
        "meson>=0.52, <1.0",
        "python-jsonrpc-server>=0.2.0,<1.0.0"
    ],
    entries={
        'console_scripts': ['mlsp=mlsp:main']
    },
    url='https://github.com/solarliner/meson-lsp',
    license='MIT',
    author='SolarLiner',
    author_email='solarliner@gmail.com',
    description='Language Server for the Meson build files'
)
