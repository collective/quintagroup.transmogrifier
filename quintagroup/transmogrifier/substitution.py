from zope.interface import classProvides, implements
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection

class SubstitutionSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.key = options['key'].strip()
        self.oldkey = "_old" + self.key
        self.options = options
        self.previous = previous

    def __iter__(self):
        key = self.key
        for item in self.previous:
            if key in item:
                old = item[key]
                new = self.options.get(item[key])
                if new is not None and old != new:
                    item[key] = new.strip()
                    item[self.oldkey] = old
            yield item
