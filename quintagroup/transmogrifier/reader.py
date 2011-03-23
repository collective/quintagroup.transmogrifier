import os
import os.path

from zope.interface import classProvides, implements
from zope.annotation.interfaces import IAnnotations

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
try:
    from collective.transmogrifier.genericsetup import IMPORT_CONTEXT
except ImportError:
    # collective.transmogrifier < 1.3
    IMPORT_CONTEXT = 'collective.transmogrifier.genericsetup.import_context'

from Products.GenericSetup import context
from Products.CMFCore import utils

# import monkey pathes for GS TarballContext
import quintagroup.transmogrifier.patches
from quintagroup.transmogrifier.logger import VALIDATIONKEY

class ReaderSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.options = options

        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

        self.pathkey = options.get('path-key', '_path').strip()
        self.fileskey = options.get('files-key', '_files').strip()
        self.contextkey = options.get('context-key', '_import_context').strip()

        if 'prefix' in options:
            self.prefix = options['prefix'].strip()
            self.prefix = self.prefix.strip(os.sep)
        else:
            self.prefix = ''

        if 'context' not in options and IMPORT_CONTEXT in self.anno:
            self.import_context = self.anno[IMPORT_CONTEXT]
        else:
            self.makeContext(options)

    def makeContext(self, options):
        context_type = options.get('context', 'tarball').strip()
        if context_type not in ['directory', 'tarball', 'snapshot']:
            context_type = 'tarball'

        path = options.get('path', '').strip()

        setup_tool = utils.getToolByName(self.context, 'portal_setup')
        if context_type == 'directory':
            self.import_context = context.DirectoryImportContext(setup_tool, path)
        elif context_type == 'tarball':
            if os.path.exists(path):
                archive = file(path, 'rb')
                archive_bits = archive.read()
                archive.close()
            else:
                archive_bits = ''
            self.import_context = context.TarballImportContext(setup_tool, archive_bits)
        elif context_type == 'snapshot':
            self.import_context = context.SnapshotImportContext(setup_tool, path)

    def walk(self, top):
        names = self.import_context.listDirectory(top)
        if names is None:
            names = []
        paths = (os.path.join(top, name) for name in names)
        dirs = [path for path in paths if self.import_context.isDirectory(path)]
        for path in dirs:
            yield self.readFiles(path)
        for path in dirs:
            for i in self.walk(path):
                yield i

    def readFiles(self, top, names=None):
        if names is None:
            names = self.import_context.listDirectory(top)
            if names is None:
                names = []
        path = top[len(self.prefix):]
        path = path.lstrip(os.sep)
        item = {self.pathkey: '/'.join(path.split(os.sep))}
        for name in names:
            full_name = os.path.join(top, name)
            if self.import_context.isDirectory(full_name): continue
            section = self.options.get(name, name).strip()
            files = item.setdefault(self.fileskey, {})
            files[section] = {
                'name': name,
                'data': self.import_context.readDataFile(name, top)
            }
        return item

    def __iter__(self):
        for item in self.previous:
            yield item

        item = self.readFiles(self.prefix)
        item[self.contextkey] = self.import_context
        self.storage.append(item[self.pathkey])
        yield item

        for item in self.walk(self.prefix):
            # add import context to item (some next section may use it)
            item[self.contextkey] = self.import_context
            self.storage.append(item[self.pathkey])
            yield item

        if VALIDATIONKEY in self.anno:
            del self.anno[VALIDATIONKEY]
