from setuptools import setup, find_packages
import os

version = '0.2'

setup(name='quintagroup.transmogrifier',
      version=version,
      description="Plone blueprints for collective.transmogrifier pipelines.",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='Quintagroup',
      author_email='info@quintagroup.com',
      url='http://quintagroup.com',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['quintagroup'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'collective.transmogrifier',
          'plone.app.transmogrifier'
          # -*- Extra requirements: -*-
      ],
      extras_require = {
        "tests": ["collective.testcaselayer"],
      },
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
