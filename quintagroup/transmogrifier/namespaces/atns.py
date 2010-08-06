"""
    Archetypes Marshall namespace but which can safely handle
    Control Characters for you
"""
import transaction

from Products.Archetypes.interfaces import IBaseUnit
from Products.Archetypes.interfaces import IObjectField

from Products.Marshall import config
from Products.Marshall.namespaces import atns as base

from quintagroup.transmogrifier.namespaces.util import has_ctrlchars


class ATAttribute(base.ATAttribute):


    def serialize(self, dom, parent_node, instance, options={}):
        
        values = self.get(instance)
        if not values:
            return

        is_ref = self.isReference(instance)
        
        for value in values:
            node = dom.createElementNS(self.namespace.xmlns, "field")
            name_attr = dom.createAttribute("name")
            name_attr.value = self.name
            node.setAttributeNode(name_attr)
            
            # try to get 'utf-8' encoded string
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            elif IBaseUnit.providedBy(value):
                value = value.getRaw(encoding='utf-8')
            else:
                value = str(value)

            if is_ref:
                if config.HANDLE_REFS:
                    ref_node = dom.createElementNS(self.namespace.xmlns,
                                                    'reference')
                    uid_node = dom.createElementNS(self.namespace.xmlns,
                                                    'uid')
                    value = dom.createTextNode(value)
                    uid_node.append(value)
                    ref_node.append(uid_node)
                    node.append(ref_node)
            elif isinstance(value, str) and has_ctrlchars(value):
                value = value.encode('base64')
                attr = dom.createAttributeNS(self.namespace.xmlns,
                                             'transfer_encoding')
                attr.value = 'base64'
                node.setAttributeNode(attr)
                value_node = dom.createCDATASection(value)
                node.appendChild(value_node)
            else:
                value_node = dom.createTextNode(value)
                node.appendChild(value_node)

            field = instance.schema._fields[self.name]
            if IObjectField.providedBy(field):
                mime_attr = dom.createAttribute('mimetype')
                mime_attr.value = field.getContentType(instance)
                node.setAttributeNode(mime_attr)
        
            node.normalize()
            parent_node.appendChild(node)

        return True

    def processXmlValue(self, context, value):
        if value is None:
            return

        value = value.strip()
        if not value:
            return

        # decode node value if needed
        te = context.node.get('transfer_encoding', None)
        if te is not None:
            value = value.decode(te)

        context_data = context.getDataFor(self.namespace.xmlns)
        data = context_data.setdefault(self.name, {'mimetype': None})
        mimetype = context.node.get('mimetype', None)
        if mimetype is not None:
            data['mimetype'] = mimetype
        
        if data.has_key('value'):
            svalues = data['value']
            if not isinstance(svalues, list):
                data['value'] = svalues = [svalues]
            svalues.append(value)
            return
        else:
            data['value'] = value

    def deserialize(self, instance, ns_data, options={}):
        if not ns_data:
            return
        data = ns_data.get( self.name )
        if data is None:
            return
        values = data.get('value', None)
        if not values:
            return

	# check if we are a schema attribute
        if self.isReference( instance ):
            values = self.resolveReferences( instance, values)
            if not config.HANDLE_REFS :
                return

        field = instance.Schema()[self.name]
        mutator = field.getMutator(instance)
        if not mutator:
            # read only field no mutator, but try to set value still
            # since it might reflect object state (like ATCriteria)
            field = instance.getField( self.name ).set( instance, values )
            #raise AttributeError("No Mutator for %s"%self.name)
            return
        
        if self.name == "id":
            transaction.savepoint()
            
        mutator(values)

        # set mimetype if possible
        mimetype = data.get('mimetype', None)
        if (mimetype is not None and IObjectField.providedBy(field)):
            field.setContentType(instance, mimetype)


class Archetypes(base.Archetypes):

    def getAttributeByName(self, schema_name, context=None):
        if context is not None and schema_name not in self.at_fields:
            if not context.instance.Schema().has_key(schema_name):
                return
                raise AssertionError, \
                      "invalid attribute %s"%(schema_name)
        
        if schema_name in self.at_fields:
            return self.at_fields[schema_name]

        attribute = ATAttribute(schema_name)
        attribute.setNamespace(self)
        
        return attribute
