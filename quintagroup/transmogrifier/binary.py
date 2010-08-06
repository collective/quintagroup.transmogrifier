import traceback
from xml.dom import minidom

from zope.interface import classProvides, implements

from ZODB.POSException import ConflictError

from Products.Archetypes.interfaces import IBaseObject

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher, Condition

class FileExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()
        # only this section can add 'excluded_field' for marshalling
        #self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_fields')
        self.excludekey = options.get('exclude-key', '_excluded_fields').strip()

        self.exclude_fieldtypes = filter(None, [i.strip() for i in
                                         options.get('exclude-fieldtypes', '').splitlines()])
        self.doc = minidom.Document()
        self.condition = Condition(options.get('condition', 'python:True'),
                                   transmogrifier, name, options)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if not pathkey:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if IBaseObject.providedBy(obj):
                schema = obj.Schema()
                binary_fields = {}
                binary_field_names = []
                for field in schema.keys():
                    if obj.isBinary(field):
                        binary_field_names.append(field)
                        if not self.condition(item, context=obj, fname=field):
                            continue
                        fname, ct, data = self.extractFile(obj, field)
                        if fname == '' or data == '':
                            # empty file fields have empty filename and empty data
                            # skip them
                            continue
                        binary_fields[field] = dict(filename=fname, mimetype=ct)
                        files = item.setdefault(self.fileskey, {})
                        #key = "field-%s" % field
                        files[fname] = {
                            # now we export FileField as file with it's original name,
                            # but it may cause name collapse
                            'name': fname,
                            'data': data,
                            'content_type': ct,
                        }
                if binary_fields:
                    files['file-fields'] = {
                        'name': '.file-fields.xml',
                        'data': self.createManifest(binary_fields),
                    }
                if binary_field_names:
                    item[self.excludekey] = binary_field_names

            yield item

    def extractFile(self, obj, field):
        """ Return tuple of (filename, content_type, data)
        """
        field = obj.getField(field)
        # temporarily:
        # dirty call, I know, just lazy to get method arguments
        # TextField overrided getBaseUnit method but didn't follow API
        try:
            base_unit = field.getBaseUnit(obj, full=True)
        except TypeError:
            base_unit = field.getBaseUnit(obj)
        fname = base_unit.getFilename() 
        ct = base_unit.getContentType()
        value = base_unit.getRaw()

        return fname, ct, value

    def createManifest(self, binary_fields):
        doc = self.doc

        root = doc.createElement('manifest')
        for fname, info in binary_fields.items():
            # create field node
            field = doc.createElement('field')

            # set name attribute
            attr = doc.createAttribute('name')
            attr.value = fname
            field.setAttributeNode(attr)

            # create filename node
            filename = doc.createElement('filename')
            filename.appendChild(doc.createTextNode(info['filename']))
            field.appendChild(filename)

            # create mimetype node
            mimetype = doc.createElement('mimetype')
            mimetype.appendChild(doc.createTextNode(info['mimetype']))
            field.appendChild(mimetype)

            root.appendChild(field)

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


class FileImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')
        self.contextkey = defaultMatcher(options, 'context-key', name, 'import_context')

        self.condition = Condition(options.get('condition', 'python:True'),
                                   transmogrifier, name, options)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]
            contextkey = self.contextkey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue
            if 'file-fields' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if IBaseObject.providedBy(obj):
                try:
                    manifest = item[fileskey]['file-fields']['data']
                    for field, info in self.parseManifest(manifest).items():
                        fname = info['filename']
                        ct = info['mimetype']
                        if fname in item[fileskey]:
                            data = item[fileskey][fname]['data']
                        elif contextkey:
                            data = self.context.readDataFile("%s/%s" % (path, fname))
                            if data is None:
                                continue
                        if not self.condition(item, context=obj, fname=field,
                            filename=fname, data=data, mimetype=ct):
                            continue
                        mutator = obj.getField(field).getMutator(obj)
                        mutator(data, filename=fname, mimetype=ct)
                except ConflictError:
                    raise
                except Exception:
                    print "Exception in fileimporter section:"
                    print '-'*60
                    traceback.print_exc()
                    print '-'*60

            yield item

    def parseManifest(self, manifest):
        doc = minidom.parseString(manifest)
        fields = {}
        for elem in doc.getElementsByTagName('field'):
            field = fields.setdefault(str(elem.getAttribute('name')), {})
            for child in elem.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue
                if child.tagName == u'filename':
                    field['filename'] = child.firstChild.nodeValue.strip().encode('utf-8')
                elif child.tagName == u'mimetype':
                    field['mimetype'] = str(child.firstChild.nodeValue.strip())

        return fields
