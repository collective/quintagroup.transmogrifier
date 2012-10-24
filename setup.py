from setuptools import setup, find_packages
import os

version = '0.4'

setup(name='quintagroup.transmogrifier',
      version=version,
      description="Plone blueprints for collective.transmogrifier pipelines.",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Framework :: Zope2",
        "Framework :: Zope3",
        "Framework :: Plone",
#        "Framework :: Plone :: 4.0",
#        "Framework :: Plone :: 4.1",
#        "Framework :: Plone :: 4.2",
        "Programming Language :: Python",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: GNU General Public License (GPL)",
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
          'plone.app.transmogrifier',
          'collective.testcaselayer'
          # -*- Extra requirements: -*-
      ],
      extras_require = {
        "tests": ["collective.testcaselayer"],
      },
      entry_points="""
      # -*- Entry points: -*-
      
      [z3c.autoinclude.plugin]
      target = plone      
      """,
      )
