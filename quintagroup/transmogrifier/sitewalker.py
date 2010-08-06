from zope.interface import classProvides, implements
from zope.annotation.interfaces import IAnnotations

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import Condition

from Products.CMFCore.interfaces import IFolderish
from Products.Archetypes.interfaces import IBaseFolder

from quintagroup.transmogrifier.logger import VALIDATIONKEY

class SiteWalkerSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = options.get('path-key', '_path').strip()
        self.typekey = options.get('type-key', '_type').strip()
        self.entrieskey = options.get('entries-key', '_entries').strip()
        # this is used for communication with 'logger' section
        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

        self.condition = Condition(options.get('condition', 'python:True'),
                                   transmogrifier, name, options)

    def getContained(self, obj):
        contained = [(k, v) for k, v in obj.contentItems()
                        if self.condition(None, context=v)]
        return tuple(contained)

    def walk(self, obj):
        if IFolderish.providedBy(obj) or IBaseFolder.providedBy(obj):
            contained = self.getContained(obj)
            yield obj, tuple([(k, v.getPortalTypeName()) for k, v in contained])
            for k, v in contained:
                for x in self.walk(v):
                    yield x
        else:
            yield obj, ()

    def __iter__(self):
        for item in self.previous:
            yield item

        for obj, contained in self.walk(self.context):
            item = {
                self.pathkey: '/'.join(obj.getPhysicalPath()[2:]),
                self.typekey: obj.getPortalTypeName(),
            }
            if contained:
                item[self.entrieskey] = contained
            # add item path to stack
            self.storage.append(item[self.pathkey])
        
            yield item

        # cleanup
        if VALIDATIONKEY in self.anno:
            del self.anno[VALIDATIONKEY]
