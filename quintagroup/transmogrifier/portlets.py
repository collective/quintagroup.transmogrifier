import logging
from xml.dom import minidom

from zope.interface import classProvides, implements, providedBy
from zope.component import getUtilitiesFor, queryMultiAdapter, getUtility, \
    getMultiAdapter, adapts
from zope.component.interfaces import IFactory
from zope.app.container.interfaces import INameChooser
from zope.schema._bootstrapinterfaces import ConstraintNotSatisfied
from zope.schema.interfaces import ICollection


from plone.portlets.interfaces import ILocalPortletAssignable, IPortletManager,\
    IPortletAssignmentMapping, IPortletAssignment, ILocalPortletAssignmentManager
from plone.portlets.constants import USER_CATEGORY, GROUP_CATEGORY, \
    CONTENT_TYPE_CATEGORY, CONTEXT_CATEGORY
from plone.app.portlets.interfaces import IPortletTypeInterface
from plone.app.portlets.exportimport.interfaces import IPortletAssignmentExportImportHandler
from plone.app.portlets.exportimport.portlets import PropertyPortletAssignmentExportImportHandler

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

class PortletsExporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()

        self.doc = minidom.Document()

    def __iter__(self):
        self.portlet_schemata = dict([(iface, name,) for name, iface in 
            getUtilitiesFor(IPortletTypeInterface)])
        self.portlet_managers = list(getUtilitiesFor(IPortletManager))

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if not pathkey:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if ILocalPortletAssignable.providedBy(obj):
                data = None

                root = self.doc.createElement('portlets')

                for elem in self.exportAssignments(obj):
                    root.appendChild(elem)
                for elem in self.exportBlacklists(obj):
                    root.appendChild(elem)
                if root.hasChildNodes():
                    self.doc.appendChild(root)
                    data = self.doc.toprettyxml(indent='  ', encoding='utf-8')
                    self.doc.unlink()

                if data:
                    item.setdefault(self.fileskey, {})
                    item[self.fileskey]['portlets'] = {
                        'name': '.portlets.xml',
                        'data': data,
                    }
            yield item

    def exportAssignments(self, obj):
        assignments = []
        for manager_name, manager in self.portlet_managers:
            mapping = queryMultiAdapter((obj, manager), IPortletAssignmentMapping)
            if mapping is None:
                continue

            mapping = mapping.__of__(obj)

            for name, assignment in mapping.items():
                type_ = None
                for schema in providedBy(assignment).flattened():
                    type_ = self.portlet_schemata.get(schema, None)
                    if type_ is not None:
                        break

                if type_ is not None:
                    child = self.doc.createElement('assignment')
                    child.setAttribute('manager', manager_name)
                    child.setAttribute('category', CONTEXT_CATEGORY)
                    child.setAttribute('key', '/'.join(obj.getPhysicalPath()))
                    child.setAttribute('type', type_)
                    child.setAttribute('name', name)

                    assignment = assignment.__of__(mapping)
                    # use existing adapter for exporting a portlet assignment
                    handler = IPortletAssignmentExportImportHandler(assignment)
                    handler.export_assignment(schema, self.doc, child)

                    assignments.append(child)

        return assignments

    def exportBlacklists(self, obj):
        assignments = []
        for manager_name, manager in self.portlet_managers:
            assignable = queryMultiAdapter((obj, manager), ILocalPortletAssignmentManager)
            if assignable is None:
                continue
            for category in (USER_CATEGORY, GROUP_CATEGORY, CONTENT_TYPE_CATEGORY, CONTEXT_CATEGORY,):
                child = self.doc.createElement('blacklist')
                child.setAttribute('manager', manager_name)
                child.setAttribute('category', category)
            
                status = assignable.getBlacklistStatus(category)
                if status == True:
                    child.setAttribute('status', u'block')
                elif status == False:
                    child.setAttribute('status', u'show')
                else:
                    child.setAttribute('status', u'acquire')
                    
                assignments.append(child)

        return assignments


class PortletsImporterSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')
        self.purge = options.get('purge', 'false').strip().lower() == 'true' and True or False

    def __iter__(self):

        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue
            if 'portlets' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            # Purge assignments if 'purge' option set to true
            if self.purge:
                for name, portletManager in getUtilitiesFor(IPortletManager):
                    assignable = queryMultiAdapter((obj, portletManager), IPortletAssignmentMapping)
                    if assignable is not None:
                        for key in list(assignable.keys()):
                            del assignable[key]

            if ILocalPortletAssignable.providedBy(obj):
                data = None
                data = item[fileskey]['portlets']['data']
                doc = minidom.parseString(data)
                root = doc.documentElement
                for elem in root.childNodes:
                    if elem.nodeName == 'assignment':
                        self.importAssignment(obj, elem)
                    elif elem.nodeName == 'blacklist':
                        self.importBlacklist(obj, elem)

            yield item

    def importAssignment(self, obj, node):
        """ Import an assignment from a node
        """
        # 1. Determine the assignment mapping and the name
        manager_name = node.getAttribute('manager')

        manager = getUtility(IPortletManager, manager_name)
        mapping = getMultiAdapter((obj, manager), IPortletAssignmentMapping)
        if mapping is None:
            return

        # 2. Either find or create the assignment
        assignment = None
        name = node.getAttribute('name')
        if name:
            assignment = mapping.get(name, None)

        type_ = node.getAttribute('type')

        if assignment is None:
            portlet_factory = getUtility(IFactory, name=type_)
            assignment = portlet_factory()

            if not name:
                chooser = INameChooser(mapping)
                name = chooser.chooseName(None, assignment)

            mapping[name] = assignment

        # aq-wrap it so that complex fields will work
        assignment = assignment.__of__(obj)

        # 3. Use an adapter to update the portlet settings
        portlet_interface = getUtility(IPortletTypeInterface, name=type_)
        assignment_handler = IPortletAssignmentExportImportHandler(assignment)
        assignment_handler.import_assignment(portlet_interface, node)

    def importBlacklist(self, obj, node):
        """ Import a blacklist from a node
        """
        manager = node.getAttribute('manager')
        category = node.getAttribute('category')
        status = node.getAttribute('status')
        
        manager = getUtility(IPortletManager, name=manager)
        
        assignable = queryMultiAdapter((obj, manager), ILocalPortletAssignmentManager)
        
        if status.lower() == 'block':
            assignable.setBlacklistStatus(category, True)
        elif status.lower() == 'show':
            assignable.setBlacklistStatus(category, False)
        elif status.lower() == 'acquire':
            assignable.setBlacklistStatus(category, None)


logger = logging.getLogger('quintagroup.transmogrifier.portletsimporter')

class PortletAssignmentExportImportHandler(PropertyPortletAssignmentExportImportHandler):
    """ This adapter is needed because original fails to handle text from 
        pretty printed XML file.
    """
    adapts(IPortletAssignment)

    def extract_text(self, node):
        ''' call the original extract_text and strip the text to remove
        newlines and space character. This is necessary to import the
        pretty xml the export blueprint produces without failing to pass
        zope.schema validation
        '''
        text = super(PortletAssignmentExportImportHandler, self).extract_text(node)
        return text.strip()
