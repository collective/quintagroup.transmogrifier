import os.path
import time

from zope.interface import classProvides, implements

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

from Products.GenericSetup import context
from Products.CMFCore import utils

# import monkey pathes for GS TarballContext
import quintagroup.transmogrifier.patches

class WriterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')

        if 'prefix' in options:
            self.prefix = options['prefix'].strip()
        else:
            self.prefix = ''

        context_type = options.get('context', 'tarball').strip()

        setup_tool = utils.getToolByName(self.context, 'portal_setup')
        if context_type == 'directory':
            profile_path = options.get('path', '')
            self.export_context = context.DirectoryExportContext(setup_tool, profile_path)
        elif context_type == 'tarball':
            self.export_context = context.TarballExportContext(setup_tool)
        elif context_type == 'snapshot':
            items = ('snapshot',) + time.gmtime()[:6]
            snapshot_id = '%s-%4d%02d%02d%02d%02d%02d' % items
            self.export_context = context.SnapshotExportContext(setup_tool, snapshot_id)
        else:
            self.export_context = context.TarballExportContext(setup_tool)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey): # path doesn't exist or no data to write
                yield item; continue

            item['_export_context'] = self.export_context

            path = item[pathkey]

            item_path = os.path.join(self.prefix, path)
            item_path = item_path.rstrip('/')

            for k, v in item[fileskey].items():
                self.export_context.writeDataFile(v['name'], v['data'], 'text/xml', subdir=item_path)

            yield item
