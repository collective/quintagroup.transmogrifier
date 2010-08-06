from zope.interface import Interface

class IExportDataCorrector(Interface):
    """ Inteface for components that do some data correction on export.
    """

    def __call__(data):
        """ Correct data given in 'data' argument and return it.
        """

class IImportDataCorrector(Interface):
    """ Inteface for components that do some data correction on import.
    """

    def __call__(data):
        """ Correct data given in 'data' argument and return it.
        """
