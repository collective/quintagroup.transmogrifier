from zExceptions import BadRequest
from copy import deepcopy
from xml.dom import minidom

from zope.interface import classProvides, implements

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

from OFS.interfaces import IPropertyManager
from Products.GenericSetup.utils import PropertyManagerHelpers, NodeAdapterBase

class Helper(PropertyManagerHelpers, NodeAdapterBase):
    """ We need this class because PropertyManagerHelpers in _initProperties
        method uses _convertToBoolean and _getNodeText methods from
        NodeAdapterBase class.
    """
    
    _encoding = 'utf-8'
    
    def __init__(self):
        pass

    def _getNodeText(self, node):
        # We override method in NodeAdapterBase, because it return bad property value.
        # When properties are extracted newline charcters and indentation were added to
        # them, but these aren't stripped on import. Maybe this method doesn't handle
        # properly multiline string values, but it is needed for importing.
        text = ''
        for child in node.childNodes:
            if child.nodeName != '#text':
                continue
            text += child.nodeValue.strip()
        return text

    def _extractProperties(self):
        fragment = self._doc.createDocumentFragment()

        for prop_map in self.context._propertyMap():
            prop_id = prop_map['id']
            if prop_id == 'i18n_domain':
                continue

            # Don't export read-only nodes
            if 'w' not in prop_map.get('mode', 'wd'):
                continue

            node = self._doc.createElement('property')
            node.setAttribute('name', prop_id)

            prop = self.context.getProperty(prop_id)
            if isinstance(prop, (tuple, list)):
                for value in prop:
                    if isinstance(value, str):
                        value = value.decode(self._encoding)
                    child = self._doc.createElement('element')
                    child.appendChild(self._doc.createTextNode(value))
                    node.appendChild(child)
            else:
                if prop_map.get('type') == 'boolean':
                    prop = unicode(bool(prop))
                elif isinstance(prop, str):
                    prop = prop.decode(self._encoding)
                elif not isinstance(prop, basestring):
                    prop = unicode(prop)
                child = self._doc.createTextNode(prop)
                node.appendChild(child)

            if 'd' in prop_map.get('mode', 'wd') and not prop_id == 'title':
                prop_type = prop_map.get('type', 'string')
                node.setAttribute('type', unicode(prop_type))
                select_variable = prop_map.get('select_variable', None)
                if select_variable is not None:
                    node.setAttribute('select_variable', select_variable)

            if hasattr(self, '_i18n_props') and prop_id in self._i18n_props:
                node.setAttribute('i18n:translate', '')

            fragment.appendChild(node)

        return fragment

    def _initProperties(self, node):
        obj = self.context
        if node.hasAttribute('i18n:domain'):
            i18n_domain = str(node.getAttribute('i18n:domain'))
            obj._updateProperty('i18n_domain', i18n_domain)
        for child in node.childNodes:
            if child.nodeName != 'property':
                continue
            prop_id = str(child.getAttribute('name'))
            prop_map = obj.propdict().get(prop_id, None)

            if prop_map is None:
                if child.hasAttribute('type'):
                    val = str(child.getAttribute('select_variable'))
                    prop_type = str(child.getAttribute('type'))
                    obj._setProperty(prop_id, val, prop_type)
                    prop_map = obj.propdict().get(prop_id, None)
                else:
                    raise ValueError("undefined property '%s'" % prop_id)

            if not 'w' in prop_map.get('mode', 'wd'):
                raise BadRequest('%s cannot be changed' % prop_id)

            elements = []
            remove_elements = []
            for sub in child.childNodes:
                if sub.nodeName == 'element':
                    if len(sub.childNodes) > 0:
                        value = sub.childNodes[0].nodeValue.strip()
                        if isinstance(value, unicode):
                            value = value.encode(self._encoding)
                        if self._convertToBoolean(sub.getAttribute('remove')
                                                  or 'False'):
                            remove_elements.append(value)
                            if value in elements:
                                elements.remove(value)
                        else:
                            elements.append(value)
                            if value in remove_elements:
                                remove_elements.remove(value)

            if elements or prop_map.get('type') == 'multiple selection':
                prop_value = tuple(elements) or ()
            elif prop_map.get('type') == 'boolean':
                prop_value = self._convertToBoolean(self._getNodeText(child))
            else:
                # if we pass a *string* to _updateProperty, all other values
                # are converted to the right type
                prop_value = self._getNodeText(child).encode(self._encoding)

            if not self._convertToBoolean(child.getAttribute('purge')
                                          or 'True'):
                # If the purge attribute is False, merge sequences
                prop = obj.getProperty(prop_id)
                if isinstance(prop, (tuple, list)):
                    prop_value = (tuple([p for p in prop
                                         if p not in prop_value and
                                            p not in remove_elements]) +
                                  tuple(prop_value))

            obj._updateProperty(prop_id, prop_value)

class PropertiesExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()

        self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_properties')
        self.exclude = filter(None, [i.strip() for i in 
                              options.get('exclude', '').splitlines()])

        self.helper = Helper()
        self.doc = minidom.Document()
        self.helper._doc = self.doc

    def __iter__(self):
        helper = self.helper
        doc = self.doc

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if not pathkey:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if IPropertyManager.providedBy(obj):
                data = None
                excludekey = self.excludekey(*item.keys())[0]
                excluded_props = tuple(self.exclude)
                if excludekey:
                    excluded_props = tuple(set(item[excludekey]) | set(excluded_props))

                helper.context = obj
                node = doc.createElement('properties')
                for elem in helper._extractProperties().childNodes:
                    if elem.nodeName != 'property':
                        continue
                    if elem.getAttribute('name') not in excluded_props:
                        node.appendChild(deepcopy(elem))
                if node.hasChildNodes():
                    doc.appendChild(node)
                    data = doc.toprettyxml(indent='  ', encoding='utf-8')
                    doc.unlink()

                if data:
                    item.setdefault(self.fileskey, {})
                    item[self.fileskey]['propertymanager'] = {
                        'name': '.properties.xml',
                        'data': data,
                    }

            yield item

class PropertiesImporterSection(object):
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

        self.helper = Helper()
        self.helper._encoding = 'utf-8'

    def __iter__(self):
        helper = self.helper

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue
            if 'propertymanager' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if IPropertyManager.providedBy(obj):
                data = None
                excludekey = self.excludekey(*item.keys())[0]
                excluded_props = self.exclude
                if excludekey:
                    excluded_props = tuple(set(item[excludekey]) | set(excluded_props))

                data = item[fileskey]['propertymanager']['data']
                doc = minidom.parseString(data)
                root = doc.documentElement
                children = [k for k in root.childNodes]
                for child in children:
                    if child.nodeName != 'property':
                        continue
                    if child.getAttribute('name') in excluded_props:
                        root.removeChild(child)

                helper.context = obj
                helper._initProperties(root)

            yield item
