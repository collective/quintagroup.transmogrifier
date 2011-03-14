import itertools
import os.path
from xml.dom import minidom

from zope.interface import classProvides, implements
from zope.annotation.interfaces import IAnnotations

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

try:
    from collections import OrderedDict
except ImportError:
    from quintagroup.transmogrifier.ordereddict import OrderedDict

from quintagroup.transmogrifier.logger import VALIDATIONKEY

try:
    next(iter([]), None)
except NameError:
    # python < 2.6
    _marker = object()
    def next(iterator, default=_marker):
        try:
            return iterator.next()
        except StopIteration:
            if default is _marker:
                raise
            return default

class IteratorWithLookahead(object):
    # Adapted from http://stackoverflow.com/questions/1518097
    def __init__(self, it):
        self.it, self.nextit = itertools.tee(iter(it))
        self._advance()

    def _advance(self):
        self.lookahead = next(self.nextit, None)

    def next(self):
        self._advance()
        return next(self.it)


class ManifestExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.entrieskey = defaultMatcher(options, 'entries-key', name, 'entries')
        self.fileskey = options.get('files-key', '_files').strip()

        self.doc = minidom.Document()

    def __iter__(self):
        for item in self.previous:
            entrieskey = self.entrieskey(*item.keys())[0]
            if not entrieskey:
                yield item; continue

            manifest = self.createManifest(item[entrieskey])

            if manifest:
                item.setdefault('_files', {})
                item[self.fileskey]['manifest'] = {
                    'name': '.objects.xml',
                    'data': manifest,
                }

            yield item

    def createManifest(self, entries):
        if not entries:
            return None

        doc = self.doc
        root = doc.createElement('manifest')

        for obj_id, obj_type in entries:
            # create record
            record = doc.createElement('record')

            # set type attribute
            attr = doc.createAttribute('type')
            attr.value = obj_type
            record.setAttributeNode(attr)

            # add object id
            text = doc.createTextNode(obj_id)
            record.appendChild(text)

            root.appendChild(record)

        doc.appendChild(root)

        try:
            data = doc.toprettyxml(indent='  ', encoding='utf-8')
        except UnicodeDecodeError:
            # all comments are strings encoded in 'utf-8' and they will properly
            # saved in xml file, but if we explicitly give 'utf-8' encoding
            # UnicodeDecodeError will be raised when they have non-ascii chars
            data = doc.toprettyxml(indent='  ')

        doc.unlink()
        return data


class ManifestImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')
        self.typekey = options.get('type-key', '_type').strip()
        self.enable_source_behaviour = options.get('enable-source-behaviour', 'true') == 'true' and True or False

        # communication with logger
        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

        # we need this dictionary to store manifest data, because reader section
        # uses recursion when walking through content folders
        self.manifests = {}

        # The reader section spits out manifests in filesystem order,
        # we need to emit them in manifest order.
        self.buffer = {}

        extractor = self.iterExtractingManifests(previous)
        self.it = IteratorWithLookahead(extractor)

    def __iter__(self):
        item = None
        folder_path = None
        while True:
            if folder_path == '':
                yield item
            manifest = self.manifests.get(folder_path, {})
            for id_ in manifest.keys():
                self.bufferTo(folder_path, id_, manifest)
                item = self.buffer.pop(id_, None)
                if item is None:
                    if folder_path == '':
                        path = id_
                    else:
                        path = '/'.join([folder_path, id_])
                    self.storage.append(path)
                    item = {pathkey: path}
                item[self.typekey] = manifest[id_]
                yield item
            manifest = {}
            # consume any remaining unlisted entries of this folder
            self.bufferTo(folder_path, None, manifest)
            if self.it.lookahead is None:
                break
            item = self.it.lookahead
            pathkey = self.pathkey(*item.keys())[0]
            path = item[pathkey]
            folder_path, item_id = os.path.split(path)

        # cleanup
        if VALIDATIONKEY in self.anno:
            del self.anno[VALIDATIONKEY]

    def iterExtractingManifests(self, previous):
        for item in previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]
            if pathkey in item and fileskey in item and 'manifest' in item[fileskey]:
                path = item[pathkey]
                data = item[fileskey]['manifest']['data']
                doc = minidom.parseString(data)
                objects = OrderedDict()
                for record in doc.getElementsByTagName('record'):
                    type_ = str(record.getAttribute('type'))
                    object_id = str(record.firstChild.nodeValue.strip())
                    objects[object_id] = type_
                self.manifests[path] = objects
            yield item

    def bufferTo(self, folder_path, id_, manifest):
        self.consumeMissingPaths()
        while self.it.lookahead is not None and id_ not in self.buffer:
            item = self.it.lookahead
            pathkey = self.pathkey(*item.keys())[0]
            path = item[pathkey]
            parent, item_id = os.path.split(path)
            if folder_path != parent:
                break
            self.it.next()
            if item_id not in manifest:
                self.consumeMissingPaths()
                continue
            self.buffer[item_id] = item

    def consumeMissingPaths(self):
        while self.it.lookahead is not None:
            item = self.it.lookahead
            pathkey = self.pathkey(*item.keys())[0]
            if pathkey:
                break
            self.it.next()
