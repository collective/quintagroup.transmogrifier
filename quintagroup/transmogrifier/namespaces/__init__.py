# import Products.Marshall namespaces to ensure it's registered
# before we override it
from Products.Marshall import namespaces
namespaces # pyflakes
from Products.Marshall.handlers.atxml import ATXMLMarshaller, XmlNamespace

from atns import Archetypes
from dcns import DublinCore
from cmfns import CMF


def replaceNamespace(ns):
    """Replace namespaces by prefix"""
    if not isinstance(ns, XmlNamespace):
        ns = ns()

    nses = ATXMLMarshaller.namespaces
    prefixes = [nses.index(n) for n in nses if n.prefix == ns.prefix]
    if len(prefixes) == 0:
        return False

    idx = prefixes[0]
    nses.pop(idx)
    nses.insert(idx, ns)

replaceNamespace(DublinCore)
replaceNamespace(Archetypes)
replaceNamespace(CMF)
