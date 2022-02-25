import datetime, re
from setuptools import setup, find_packages

DESCRIPTION = 'outlook_services'
LONG_DESCRIPTION = None
try:
    LONG_DESCRIPTION = open('README.rst').read()
except:
    LONG_DESCRIPTION = ''

try:
    REQUIREMENTS = open('cap_outlook_service/requirements.txt').read()
except:
    REQUIREMENTS = []

install_requires = [r for r in REQUIREMENTS.split('\n') if r and not re.match('^ *#.*', r)] if REQUIREMENTS else []

setup(name='outlook_services',
      install_requires=install_requires,
      version='0.3.2',
      packages=[
                'cap_outlook_service.outlook_services',
                ],
      package_dir={'outlook_services': 'cap_outlook_service/outlook_services'},
      package_data={},
      author='webmaster',
      author_email='ganesh@ndimensionz.com',
      url='http://git.ndzhome.com/David/cap_outlook_service',
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      platforms=['any'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Framework :: Django/GAE',
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Application Frameworks',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
)
