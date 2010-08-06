import re
from xml.dom import minidom

from zope.interface import implements
from zope.component import adapts

from Products.Archetypes.interfaces import IBaseObject
from Products.Archetypes import atapi

from collective.transmogrifier.interfaces import ITransmogrifier

from quintagroup.transmogrifier.interfaces import IImportDataCorrector

EXISTING_UIDS = {}
REFERENCE_QUEUE = {}

class ReferenceImporter(object):
    """ Demarshall content from xml file by using of Marshall product.
    """
    implements(IImportDataCorrector)
    adapts(IBaseObject, ITransmogrifier)

    def __init__(self, context, transmogrifier):
        self.context = context
        self.transmogrifier = transmogrifier

    def __call__(self, data):
        # uid = self.context.UID()
        uid = self.getUID(data['data'])
        if uid:
            EXISTING_UIDS[uid] = None
        data['data'] = self.importReferences(data['data'])
        return data

    def getUID(self, xml):
        """ Find 'uid' element and get it's value.
        """
        start = re.search(r'<uid>', xml)
        end = re.search(r'</uid>', xml)
        if start and end:
            uid = xml[start.end():end.start()]
            return uid.strip()
        return None

    def importReferences(self, data):
        """ Marshall 1.0.0 doesn't import references, do it manually.
        """
        doc = minidom.parseString(data)
        root = doc.documentElement
        for fname in self.context.Schema().keys():
            if not isinstance(self.context.Schema()[fname], atapi.ReferenceField):
                continue
            uids = []
            validUIDs = True
            elements = [i for i in root.getElementsByTagName('field') if i.getAttribute('name') == fname]
            if not elements:
                # if needed elements are absent skip this field
                # update as much as posible fields and don't raise exceptions
                continue
            elem = elements[0]
            for uid_elem in elem.getElementsByTagName('uid'):
                value = str(uid_elem.firstChild.nodeValue)
                uids.append(value)
                if value not in EXISTING_UIDS:
                    validUIDs = False
            if validUIDs:
                mutator = self.context.Schema()[fname].getMutator(self.context)
                mutator(uids)
            else:
                suid = str(root.getElementsByTagName('uid')[0].firstChild.nodeValue.strip())
                REFERENCE_QUEUE[suid] = {}
                REFERENCE_QUEUE[suid][fname] = uids
            root.removeChild(elem)
        return doc.toxml('utf-8')
