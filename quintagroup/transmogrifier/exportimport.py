# -*- coding: utf-8 -*-
import os
import tempfile

from zope.interface import implements
from zope.annotation import IAnnotations

from collective.transmogrifier.interfaces import ITransmogrifier
from collective.transmogrifier.transmogrifier import _load_config, constructPipeline
from collective.transmogrifier.transmogrifier import configuration_registry

from Products.GenericSetup.context import TarballExportContext, TarballImportContext
from Products.GenericSetup.interfaces import IFilesystemImporter

from quintagroup.transmogrifier.writer import WriterSection
from quintagroup.transmogrifier.reader import ReaderSection
from quintagroup.transmogrifier.configview import ANNOKEY

EXPORT_CONFIG = 'export'
IMPORT_CONFIG = 'import'

CONFIGFILE = None
def registerPersistentConfig(site, type_):
    """ Try to get persistent pipeline configuration of given type (export or import)
        and register it for use with transmogrifier.
    """
    global CONFIGFILE
    anno = IAnnotations(site)
    key = '%s.%s' % (ANNOKEY, type_)
    config = anno.has_key(key) and anno[key] or None

    # unregister old config
    name = 'persitent-%s' % type_
    if name in configuration_registry._config_ids:
        configuration_registry._config_ids.remove(name)
        del configuration_registry._config_info[name]

    # register new
    if config is not None:
        title = description = u'Persistent %s pipeline'
        tf = tempfile.NamedTemporaryFile('w+t', suffix='.cfg')
        tf.write(config)
        tf.seek(0)
        CONFIGFILE = tf
        configuration_registry.registerConfiguration(name, title, description, tf.name)
        return name
    else:
        return None

def exportSiteStructure(context):

    transmogrifier = ITransmogrifier(context.getSite())

    # we don't use transmogrifer's __call__ method, because we need to do
    # some modification in pipeline sections

    config_name = registerPersistentConfig(context.getSite(), 'export')
    if config_name is None:
        transmogrifier._raw = _load_config(EXPORT_CONFIG)
    else:
        transmogrifier._raw = _load_config(config_name)
        global CONFIGFILE
        CONFIGFILE = None
    transmogrifier._data = {}

    options = transmogrifier._raw['transmogrifier']
    sections = options['pipeline'].splitlines()
    pipeline = constructPipeline(transmogrifier, sections)

    last_section = pipeline.gi_frame.f_locals['self']

    # if 'quintagroup.transmogrifier.writer' section's export context is
    # tarball replace it with given function argument
    while hasattr(last_section, 'previous'):
        if isinstance(last_section, WriterSection) and \
            isinstance(last_section.export_context, TarballExportContext):
            last_section.export_context = context
        last_section = last_section.previous
        # end cycle if we get empty starter section
        if type(last_section) == type(iter(())):
            break
        last_section = last_section.gi_frame.f_locals['self']

    # Pipeline execution
    for item in pipeline:
        pass # discard once processed

def importSiteStructure(context):

    # Only run step if a flag file is present
    if context.readDataFile('quintagroup.transmogrifier-import.txt') is None:
        if getattr(context, '_archive', None) is None:
            return

    transmogrifier = ITransmogrifier(context.getSite())

    # we don't use transmogrifer's __call__ method, because we need to do
    # some modification in pipeline sections

    config_name = registerPersistentConfig(context.getSite(), 'import')
    if config_name is None:
        transmogrifier._raw = _load_config(IMPORT_CONFIG)
    else:
        transmogrifier._raw = _load_config(config_name)
        global CONFIGFILE
        CONFIGFILE = None
    transmogrifier._data = {}

    # this function is also called when adding Plone site, so call standard handler
    path = ''
    prefix = 'structure'
    if 'reader' in transmogrifier._raw:
        path = transmogrifier._raw['reader'].get('path', '')
        prefix = transmogrifier._raw['reader'].get('prefix', 'structure')
    if not context.readDataFile('.objects.xml', subdir=os.path.join(path, prefix)):
        try:
            from Products.GenericSetup.interfaces import IFilesystemImporter
            IFilesystemImporter(context.getSite()).import_(context, 'structure', True)
        except ImportError:
            pass
        return

    options = transmogrifier._raw['transmogrifier']
    sections = options['pipeline'].splitlines()
    pipeline = constructPipeline(transmogrifier, sections)

    last_section = pipeline.gi_frame.f_locals['self']

    # if 'quintagroup.transmogrifier.writer' section's export context is
    # tarball replace it with given function argument
    while hasattr(last_section, 'previous'):
        if isinstance(last_section, ReaderSection) and \
            isinstance(last_section.import_context, TarballImportContext):
            last_section.import_context = context
        last_section = last_section.previous
        # end cycle if we get empty starter section
        if type(last_section) == type(iter(())):
            break
        last_section = last_section.gi_frame.f_locals['self']

    # Pipeline execution
    for item in pipeline:
        pass # discard once processed


class PloneSiteImporter(object):
    """ Importer of plone site.
    """
    implements(IFilesystemImporter)

    def __init__(self, context):
        self.context = context

    def import_(self, import_context, subdir="structure", root=False):
        # When performing import steps we need to use standart importing adapter,
        # if 'object.xml' file is absent in 'structure' directory of the profile.
        # This may be because it is the base plone profile or extension profile, that has
        # structure part in other format.

        objects_xml = import_context.readDataFile('.objects.xml', subdir)
        if objects_xml is not None:
            importSiteStructure(import_context)
        else:
            from Products.CMFCore.exportimport.content import StructureFolderWalkingAdapter
            StructureFolderWalkingAdapter(self.context).import_(import_context, "structure", True)
