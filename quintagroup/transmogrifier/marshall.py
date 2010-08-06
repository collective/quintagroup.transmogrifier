import traceback

from zope.interface import classProvides, implements
from zope import event

from ZODB.POSException import ConflictError

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import defaultMatcher

from Products.CMFCore import utils
from Products.Marshall import registry
from Products.Archetypes.interfaces import IBaseObject
from Products.Archetypes.event import ObjectInitializedEvent
from Products.Archetypes.event import ObjectEditedEvent


class MarshallerSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()

        self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_fields')
        self.exclude = filter(None, [i.strip() for i in 
                              options.get('exclude', '').splitlines()])

        self.atxml = registry.getComponent("atxml")

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
                # get list of excluded fields given in options and in item
                excludekey = self.excludekey(*item.keys())[0]
                atns_exclude = tuple(self.exclude)
                if excludekey:
                    atns_exclude = tuple(set(item[excludekey]) | set(atns_exclude))

                try:
                    content_type, length, data = self.atxml.marshall(obj, atns_exclude=atns_exclude)
                except ConflictError:
                    raise
                except Exception:
                    data = None

                if data or data is None:
                    # None value has special meaning for IExportDataCorrector adapter for topic criterias
                    item.setdefault(self.fileskey, {})
                    item[self.fileskey]['marshall'] = {
                        'name': '.marshall.xml',
                        'data': data,
                    }

            yield item

class DemarshallerSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')

        # Marshall doesn't support excluding fields on demarshalling,
        # we can do this with xml.dom.minodom, if it'll be needed in the future
        # self.excludekey = defaultMatcher(options, 'exclude-key', name, 'excluded_fields')

        # self.exclude = filter(None, [i.strip() for i in 
        #                     options.get('exclude', '').splitlines()])

        self.atxml = registry.getComponent("atxml")

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            fileskey = self.fileskey(*item.keys())[0]

            if not (pathkey and fileskey):
                yield item; continue
            if 'marshall' not in item[fileskey]:
                yield item; continue

            path = item[pathkey]
            obj = self.context.unrestrictedTraverse(path, None)
            if obj is None:         # path doesn't exist
                yield item; continue

            if IBaseObject.providedBy(obj):
                try:
                    data = item[fileskey]['marshall']['data']
                    self.atxml.demarshall(obj, data)

                    # When we change workflow state of content through Plone interface,
                    # effective date field will be updated to current date (the same
                    # as modification date) if it was empty, so after demarshalling
                    # (workflow history was updated) we need to do it manually.
                    effective_field = obj.getField('effectiveDate')
                    if effective_field is not None and effective_field.getAccessor(obj)() is None:
                        date = obj.getField('modification_date').getAccessor(obj)()
                        effective_field.getMutator(obj)(date)

                    # we don't want to call reindexObject because modification_date
                    # will be updated, so we call only indexObject (reindexObject does
                    # some things with uid catalog too)
                    is_new_object = obj.checkCreationFlag()
                    obj.indexObject()
                    # firing of events
                    obj.unmarkCreationFlag()
                    if is_new_object:
                        event.notify(ObjectInitializedEvent(obj))
                        obj.at_post_create_script()
                    else:
                        event.notify(ObjectEditedEvent(obj))
                        obj.at_post_edit_script()
                except ConflictError:
                    raise
                except Exception:
                    print 'Exception in demarshaller section:'
                    print '-'*60
                    traceback.print_exc()
                    print '-'*60

            yield item

        # updating security settings on demarshalled content
        wtool = utils.getToolByName(self.context, 'portal_workflow')
        wtool.updateRoleMappings()
        catalog = utils.getToolByName(self.context, 'portal_catalog')
        catalog.reindexIndex('allowedRolesAndUsers', None)
