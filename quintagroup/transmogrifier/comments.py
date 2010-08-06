from xml.dom import minidom

from zope.interface import classProvides, implements

from Acquisition import aq_base
from Products.CMFCore import utils
from Products.CMFDefault import DiscussionItem
from Products.CMFDefault.exceptions import DiscussionNotAllowed

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

class CommentsExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()

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

            # check if object has comments
            discussion_container = getattr(aq_base(obj), 'talkback', None)
            if discussion_container is not None:
                data = self.extractComments(discussion_container)
                if data:
                    item.setdefault(self.fileskey, {})
                    item[self.fileskey]['comments'] = {
                        'name': '.comments.xml',
                        'data': data,
                    }

            yield item

    def extractComments(self, container):
        doc = self.doc

        items = container.objectItems()
        if not items:
            return None

        root = doc.createElement('discussion')
        doc.appendChild(root)
        for item_id, item in items:
            hdrlist = item.getMetadataHeaders()
            # get creator (it is displayed in "Posted by")
            hdrlist.append(('Creator', item.Creator()))
            # get modification date (also is displayed)
            hdrlist.append(('Modification_date', item.ModificationDate()))
            # get relation
            hdrlist.append(('In_reply_to', str(item.in_reply_to)))
            # get comment text
            hdrlist.append(('Text', item.text))

            item_elem = doc.createElement('item')
            attr = doc.createAttribute('id')
            attr.value = item_id
            item_elem.setAttributeNode(attr)

            for k, v in hdrlist:
                field = doc.createElement('field')
                attr = doc.createAttribute('name')
                attr.value = k
                field.setAttributeNode(attr)
                text = doc.createTextNode(v)
                field.appendChild(text)
                item_elem.appendChild(field)

            root.appendChild(item_elem)


        try:
            data = self.doc.toprettyxml(indent='  ', encoding='utf-8')
        except UnicodeError:
            # all comments are strings encoded in 'utf-8' and they will properly
            # saved in xml file, but if we explicitly give 'utf-8' encoding
            # UnicodeDecodeError will be raised when they have non-ascii chars
            data = self.doc.toprettyxml(indent='  ')

        self.doc.unlink()
        return data

class CommentsImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')

        self.dtool = utils.getToolByName(self.context, 'portal_discussion')

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue

            if 'comments' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            # allow discussion if it wasn't allowed (because we have comments)
            try:
                discussion_container = self.dtool.getDiscussionFor(obj)
            except DiscussionNotAllowed:
                obj.allow_discussion = True
                discussion_container = self.dtool.getDiscussionFor(obj)

            data = item[fileskey]['comments']['data']
            discussion_container._container.clear()
            for id_, props in self.parseXML(data).items():
                comment = DiscussionItem.DiscussionItem(id_)
                discussion_container._container[id_] = comment
                comment = comment.__of__(discussion_container)
                self.updateDiscussionItem(comment, props)

            yield item

    def parseXML(self, data):
        doc = minidom.parseString(data)
        root = doc.documentElement

        items = {}
        for child in root.childNodes:
            if child.nodeName != 'item':
                continue
            id_ = str(child.getAttribute('id'))
            item = items[id_] = {}
            for field in child.childNodes:
                if field.nodeName != 'field':
                    continue
                name = field.getAttribute('name')
                # this will be unicode string, encode it?
                value = ''
                for node in field.childNodes:
                    if node.nodeName != '#text':
                        continue
                    lines = [line.lstrip() for line in node.nodeValue.splitlines()]
                    value += '\n'.join(lines)
                item[name] = value.strip()

        return items

    def updateDiscussionItem(self, item, props):
        in_reply_to = props['In_reply_to']
        # if 'In_reply_to' field is string "None" we need to set attribute to None
        if in_reply_to == 'None':
            item.in_reply_to = None
        else:
            item.in_reply_to = in_reply_to

        item.addCreator(props['Creator'])
        item.setFormat('text/plain')
        item.setMetadata(props)
        item._edit(text=props['Text'])
        item.setModificationDate(props['Modification_date'])
        item.indexObject()
