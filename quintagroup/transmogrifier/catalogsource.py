__docformat__ = "epytext"

import copy
import logging

from zope.interface import classProvides, implements
from zope.annotation.interfaces import IAnnotations

from collective.transmogrifier.interfaces import ISection, ISectionBlueprint

from Products.CMFCore import utils

from quintagroup.transmogrifier.logger import VALIDATIONKEY

logger = logging.getLogger("CatalogSourceSection")

class CatalogSourceSection(object):
    """
    
    Parameters:
    
        * *exclude-contained*: do not export child objects if they do not match the catalog query source.
          This is useful with path based queries where you do not wish to export items of each parent 
          folder. 
    
    For other parameteres, please consult the original authors
    anad pledge them to comment what they have intended to do with this code.
    
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        # next is for communication with 'logger' section
        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])

        self.pathkey = options.pop('path-key', '_path')
        self.entrieskey = options.pop('entries-key', '_entries')

        # Handle exclude-contained parameter
        if "exclude-contained" in options.keys():
            self.exclude_contained = options.pop('exclude-contained')
            self.exclude_contained = self.exclude_contained == "true"
        else:
            self.exclude_contained = False 

        # remove 'blueprint' option - it cannot be a query
        options.pop('blueprint')

        self.query = {}
        for k, v in options.items():
            for p in v.split(';'):
                params = p.split('=', 1)
                if len(params) == 1:
                    self.query[k] = p.strip()
                else :
                    q = self.query.setdefault(k, {})
                    q[params[0].strip()] = params[1].strip()

        self.catalog = utils.getToolByName(self.context, 'portal_catalog')

    def __iter__(self):
        for item in self.previous:
            yield item

        exported = []
        exported_parents = []
        
        results = list(self.catalog(**self.query))
        results.sort(key=lambda x: x.getPath())
        
        for brain in results:
            # discussion items are indexed and they must be replaced to
            # content objects to which they correspond
            # we need to skip them
            if brain.portal_type == 'Discussion Item':
                path =  '/'.join(brain.getPath().split('/')[:-2])
                cp, id_ = path.rsplit('/', 1)
                brain = self.catalog(path=cp, id=id_)[0]
            else:
                path = brain.getPath()

            # folderish objects are tried to export twice:
            # when their contained items are exported and when they are
            # returned in catalog search results
            if path in exported:
                continue
            exported.append(path)

            # export also all parents of current object
            containers = []
            container_path = path.rsplit('/', 1)[0]
            while container_path:
                
                if container_path in exported:
                    container_path = container_path.rsplit('/', 1)[0]
                    continue
                
                exported_parents.append(container_path)
                                
                contained = self.getContained(container_path, results, exported_parents)
              
                if contained:
                    exported.append(container_path)
                    containers.append({
                        self.pathkey: '/'.join(container_path.split('/')[2:]),
                        self.entrieskey: contained,
                    })
                container_path = container_path.rsplit('/', 1)[0]
            
            containers.reverse()
            # order metter for us
            for i in containers:
                self.storage.append(i[self.pathkey])
                yield i

            item = {
                self.pathkey: '/'.join(path.split('/')[2:]),
            }
            if brain.is_folderish:
                contained = self.getContained(path, results, exported_parents)
                if contained:
                    item[self.entrieskey] = contained

            self.storage.append(item[self.pathkey])
            # try to export entire Collection with criteria
            try:
                obj = self.context.restrictedTraverse(path)
                if obj.Type() == 'Collection':
                    for crit in contained:
                        yield {'_type':crit[1], '_path':item['_path']+'/'+crit[0]}
            except:
                logging.info("ERROR Traversing obj: %s"%path)
            yield item

        # cleanup
        if VALIDATIONKEY in self.anno:
            del self.anno[VALIDATIONKEY]

    def getContained(self, path, original_results, parents):
        """ Return list of (object_id, portal_type) for objects that are returned by catalog
            and contained in folder with given 'path'.
        
        @param original_results: Orignal portal_catalog result set - filter out child objects if they are not in this set.
                                Set to None if you do not wish to filter the results. 
        
        """
        results = []
        seen = []
        
       
        # Remove the original path element from the query if there was one 
        query = copy.deepcopy(self.query)
        if "path" in query:
            del query["path"]
        
        raw_results = self.catalog(path=path, **query)
        
        for brain in raw_results:
            current = brain.getPath()
            relative = current[len(path):]
            relative = relative.strip('/')
            if not relative:
                # it's object with path that was given in catalog query
                continue
            elif '/' in relative:
                # object stored in subfolders, we need append to results their parent folder
                parent_path = '/'.join([path, relative.split('/', 1)[0]])
                if parent_path not in seen:                    
                    res = self.catalog(path=path) #, meta_type='Folder')
                    for i in res:
                        if i.getPath() == parent_path:
                            results.append(i)
                            seen.append(parent_path)
                            break
            elif current not in seen:
                # object is directly stored in folder, that has path given in query
                seen.append(current)
                results.append(brain)

        # Work around the issue if our catalog query has been by path
        # -> do not include path search term twice in the query.
        # Note that this may lead to incorrect results
        # for complex path queries.
        # This prevents us having extra items in .objects.xml
        # which do not actually appear in the exported content items.

        def filter(r):
            
            # Parent objects must be allowed always
            for parent in parents:
                #print parent
                #print r.getPath()
                if r.getPath() == parent:
                    return True
            
            if r["UID"] in allowed_uids:
                return True
            else:
                logger.info("Excluded contained item as it did not match the original catalog query:" + str(r.getPath()))

        if self.exclude_contained and original_results is not None:
            # Filter contained results against our query, so that
            # we do not export results from parent objects which did not match
            # Build list of allowed object UIDs -
            allowed_uids = [ r["UID"] for r in original_results ]
            
            # All parents must be allowed always            
            filtered_results = [ r for r in results if filter(r) == True  ]
        else:
            # Don't filter child items
            filtered_results = results
        
        contained = [(i.getId, str(i.portal_type)) for i in filtered_results ]

        # list Collection criteria
        try:
            obj = self.context.restrictedTraverse(str(path), None)
            if obj.Type() == 'Collection':
                contained = [(str(i.id), str(i.portal_type)) for i in obj.objectValues()]
        except:
            logging.info("ERROR Traversing obj: %s"%path)
                     
        return tuple(contained)
