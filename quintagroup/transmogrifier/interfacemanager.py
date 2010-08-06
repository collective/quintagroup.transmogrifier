from xml.dom import minidom

from zope.interface import classProvides, implements
from zope.interface import directlyProvidedBy, alsoProvides

from Products.CMFCore import utils

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

class InterfacesExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()

        self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_interfaces')
        self.exclude = filter(None, [i.strip() for i in
                              options.get('exclude', '').splitlines()])

        self.includekey = defaultMatcher(options, 'include-key', name, 'included_interfaces')
        self.include = filter(None, [i.strip() for i in
                              options.get('include', '').splitlines()])

        self.doc = minidom.Document()

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if not pathkey:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            ifaces = self.getInterfaces(obj)

            if ifaces:
                item.setdefault('_files', {})
                item[self.fileskey]['interfaces'] = {
                    'name': '.interfaces.xml',
                    'data': ifaces,
                }

            yield item

    def getInterfaces(self, obj):
        if not obj:
            return None

        doc = self.doc
        root = doc.createElement('interfaces')

        ifaces = [i.__identifier__ for i in directlyProvidedBy(obj)]
        if self.include:
            ifaces = filter(lambda i: i in self.include, ifaces)
        elif self.exclude:
            ifaces = filter(lambda i: not i in self.include, ifaces)

        if ifaces == []:
            return None

        for iface in ifaces:
            # create record
            record = doc.createElement('record')

            # add object interface
            text = doc.createTextNode(iface)
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


class InterfacesImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')

        self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_properties')
        self.exclude = filter(None, [i.strip() for i in
                            options.get('exclude', '').splitlines()])

        self.includekey = defaultMatcher(options, 'include-key', name, 'included_properties')
        self.include = filter(None, [i.strip() for i in
                              options.get('include', '').splitlines()])

        self.catalog = utils.getToolByName(self.context, 'portal_catalog')

    def __iter__(self):

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue
            if 'interfaces' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            ifaces = self.extractIfaces(obj, item[fileskey]['interfaces']['data'])

            if ifaces == []:         # no interfaces
                yield item; continue

            alsoProvides(obj, *ifaces)

            yield item

        self.catalog.reindexIndex('object_provides', None)


    def extractIfaces(self, obj, data):
        doc = minidom.parseString(data)
        ifaces = []
        for record in doc.getElementsByTagName('record'):
            iface_name = str(record.firstChild.nodeValue.strip())

            # filter interfaces
            if self.include and not iface_name in self.include:
                continue
            elif self.exclude and iface_name in self.exclude:
                continue
                
            iface = self.getIfaceById(iface_name)
            if iface:
                ifaces.append(iface)
        return ifaces


    def getIfaceById(self, name):
        components = name.split('.'); components.reverse()
        try:
            obj = __import__(components.pop())
        except (ImportError, ValueError):
            return None
        while obj is not None and components:
            obj = getattr(obj, components.pop(), None)
        return obj

