from setuptools import setup, find_packages

setup(
    name='mywhisper',
    version='0.7.2',
    packages=find_packages(),
    install_requires=[
        'pydub',
        'speechrecognition',
        'torch',
        'numpy',
        # 'pyaudio',
    ],
    url='https://github.com/lupin-oomura/mywhisper.git',
    author='Shin Oomura',
    author_email='shin.oomura@gmail.com',
    description='A simple OpenAI function package',
)
