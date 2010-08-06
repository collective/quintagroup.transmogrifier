"""
    DublinCore Marshall namespace but which can safely handle
    Control Characters for you
"""

from Products.Archetypes.interfaces import IBaseUnit

from Products.Marshall.namespaces import dcns as base
from Products.Marshall.namespaces.dcns import normalizer

from quintagroup.transmogrifier.namespaces.util import has_ctrlchars


class DCAttribute(base.DCAttribute):

    def serialize(self, dom, parent_node, instance):
        values = self.get(instance)
        if not values:
            return False
        
        for value in values:
            elname = "%s:%s"%(self.namespace.prefix, self.name)
            node = dom.createElementNS(base.DublinCore.xmlns, elname)

            # try to get 'utf-8' encoded string
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            elif IBaseUnit.providedBy(value):
                value = value.getRaw(encoding='utf-8')
            else:
                value = str(value)

            if isinstance(value, str) and has_ctrlchars(value):
                value = value.encode('base64')
                attr = dom.createAttributeNS(base.DublinCore.xmlns,
                                             'transfer_encoding')
                attr.value = 'base64'
                node.setAttributeNode(attr)
                value_node = dom.createCDATASection(value)
            else:
                value_node = dom.createTextNode(value)

            node.appendChild(value_node)
            node.normalize()
            parent_node.appendChild(node)
        return True

    def processXmlValue(self, context, value):
        value = value and value.strip()
        if not value:
            return

        # decode node value if needed
        te = context.node.get('transfer_encoding', None)
        if te is not None:
            value = value.decode(te)

        data = context.getDataFor(self.namespace.xmlns)
        if self.many:
            data.setdefault(self.name, []).append(value)
        else:
            data[self.name]=value

class DublinCore(base.DublinCore):
    
    attributes = (
        DCAttribute('title', 'Title', 'setTitle',
                    process=(normalizer.space, normalizer.newline)),
        
        DCAttribute('description', 'Description', 'setDescription',
                    process=(normalizer.space,)),

        DCAttribute('subject', 'Subject', 'setSubject', many=True),                
        DCAttribute('contributor', 'Contributors', 'setContributors',
                    many=True),
        # this attr diverges from cmfdefault.dublincore
        DCAttribute('creator', 'Creators', 'setCreators', many=True),
        DCAttribute('rights', 'Rights', 'setRights'),
        DCAttribute('language', 'Language', 'setLanguage')
        )
