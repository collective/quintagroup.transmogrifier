try:
    import libxml2
    import libxslt
except ImportError:
    HAS_LIBS = False
else:
    HAS_LIBS = True

from zope.interface import classProvides, implements, Interface
from zope.configuration.fields import Path
from zope.schema import TextLine

from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.utils import defaultMatcher

class StylesheetRegistry(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self._stylesheet_info = {}

    def registerStylesheet(self, source, from_, to, file):
        name = "%s:%s" % (from_, to)
        if source in self._stylesheet_info:
            if name in self._stylesheet_info[source]:
                raise KeyError('Duplicate stylesheet registration: %s %s %s' % 
                    (source, from_, to))
        source = self._stylesheet_info.setdefault(source, {})
        source[name] = {
            'from_': from_,
            'to': to,
            'file': file
        }

    def getStylesheet(self, source, from_, to):
        name = "%s:%s" % (from_, to)
        try:
            return self._stylesheet_info[source][name]
        except KeyError:
            return None

    def listStylesheetNames(self):
        names = []
        for k, v in self._stylesheet_info.items():
            for name in v.keys():
                names.append("%s:%s" % (k, name))
        return tuple(names)

stylesheet_registry = StylesheetRegistry()

# Test cleanup support
from zope.testing.cleanup import addCleanUp
addCleanUp(stylesheet_registry.clear)
del addCleanUp

class IStylesheetDirective(Interface):
    """ Register XSLT file with the global registry.
    """

    source = TextLine(
        title=u"Source",
        description=u"The source of XML data.",
        required=True
        )

    from_ = TextLine(
        title=u"From",
        description=u"Value which describes XML data before transformation.",
        required=True
        )

    to = TextLine(
        title=u"To",
        description=u"Value which describes XML data after transformation.",
        required=True
        )

    file = Path(
        title=u"XSLT file",
        description=u"The XSLT file to register.",
        required=True
        )


def stylesheet(_context, source, from_, to, file):
    """Add a new stylesheet to the registry"""

    _context.action(
        discriminator=('stylesheet', source, from_, to),
        callable=stylesheet_registry.registerStylesheet,
        args=(source, from_, to, file))


class XSLTSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.fileskey = defaultMatcher(options, 'files-key', name, 'files')
        self.source = options.get('source', 'marshall').strip()
        self.fromkey = defaultMatcher(options, 'from-key', name, 'from')
        self.tokey = defaultMatcher(options, 'to-key', name, 'to')

        self.previous = previous

    def __iter__(self):
        source = self.source
        for item in self.previous:
            fileskey = self.fileskey(*item.keys())[0]
            fromkey = self.fromkey(*item.keys())[0]
            tokey = self.tokey(*item.keys())[0]

            if not (fileskey and fromkey and tokey):
                yield item; continue

            if not (source in item[fileskey] and item[fileskey][source]):
                yield item; continue

            from_ = item[fromkey]
            to = item[tokey]
            stylesheet_info = stylesheet_registry.getStylesheet(source, from_, to)

            if stylesheet_info is None:
                yield item; continue

            fp = open(stylesheet_info['file'], 'r')
            stylesheet = fp.read()
            fp.close()

            source_dict = item[fileskey][source]
            source_dict['data'] = self.applyTransformations(source_dict['data'], stylesheet)

            yield item

    def applyTransformations(self, xml, xslt):
        if not HAS_LIBS:
            raise RuntimeError("Can't apply transformations, libxml2/libxslt packages are not available")
        # parse document
        doc = libxml2.parseDoc(xml)
        # parse stylesheet
        styledoc = libxml2.parseDoc(xslt)
        # make style object
        style = libxslt.parseStylesheetDoc(styledoc)
        # apply style to document
        result = style.applyStylesheet(doc, None)
        # write result to a file
        transformed = style.saveResultToString(result)
        # free all documents
        style.freeStylesheet()
        doc.freeDoc()
        result.freeDoc()
        return transformed
