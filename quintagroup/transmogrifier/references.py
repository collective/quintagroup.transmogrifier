from zope.interface import classProvides, implements

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint

from Products.CMFCore.utils import getToolByName
from Products.Archetypes import config as atcfg

# most reference importing actions are done in adapter, what can't be done is saved in
# next global variables (this must be changed)
from quintagroup.transmogrifier.adapters.importing import EXISTING_UIDS, REFERENCE_QUEUE

class ReferencesImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

    def __iter__(self):
        for item in self.previous:
            yield item
        # finalization of importing references
        rc = getToolByName(self.context, atcfg.REFERENCE_CATALOG)
        uc = getToolByName(self.context, atcfg.UID_CATALOG)
        uids = uc.uniqueValuesFor('UID')
        existing = set(uids)
        for suid, rel_fields in REFERENCE_QUEUE.items():
            instance = rc.lookupObject(suid)
            for fname, tuids in rel_fields.items():
                # now we update reference field only if all target UIDs are valid
                # but may be it is better to update with as much as possible valid
                # target UIDs (do existing.intersection(set(tuids)))
                if set(tuids).issubset(existing):
                    mutator = instance.Schema()[fname].getMutator(instance)
                    mutator(tuids)
        EXISTING_UIDS.clear()
        REFERENCE_QUEUE.clear()
