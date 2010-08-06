from zope.annotation import IAnnotations

from Products.Five.browser import BrowserView

from collective.transmogrifier.transmogrifier import configuration_registry

ANNOKEY = 'quintagroup.transmogrifier.config'

class PipelineConfigView(BrowserView):
    """ View for setting persistent pipeline config.
    """

    def __init__(self, context, request):
        super(PipelineConfigView, self).__init__(context, request)
        self.anno = IAnnotations(context)
        self.status = None

    def __call__(self):
        action = self.request.form.get('action')
        if action is not None:
            stat = []
            # handle export config
            export_config = self.request.form['export'].strip()
            expkey = ANNOKEY+'.export'
            oldconfig = self.getConfig('export')
            if export_config and self._configChanged(oldconfig, export_config):
                self.anno[expkey] = export_config
                stat.append('updated export')
            elif not export_config and expkey in self.anno:
                del self.anno[expkey]
                stat.append('removed export')
            # handle import config
            import_config = self.request.form['import'].strip()
            impkey = ANNOKEY+'.import'
            oldconfig = self.getConfig('import')
            if import_config and self._configChanged(oldconfig, import_config):
                self.anno[impkey] = import_config
                stat.append('updated import')
            elif not import_config and impkey in self.anno:
                del self.anno[impkey]
                stat.append('removed import')
            if stat:
                self.status = 'Changes: %s configuration.' % ' and '.join(stat)
            else:
                self.status = 'No changes'

        return self.index()

    def getConfig(self, type_):
        key = '%s.%s' % (ANNOKEY, type_)
        if key in self.anno:
            return self.anno[key]
        else:
            fname = configuration_registry.getConfiguration(type_)['configuration']
            return file(fname).read()

    def _configChanged(self, old, new):
        """ Compare configs with normalization of line endings.
        """
        if old == new:
            return False
        if old == new.replace('\r\n', '\n'):
            return False
        if old.strip() == new.replace('\r\n', '\n'):
            return False
        return True

    def isDefault(self, type_):
        key = '%s.%s' % (ANNOKEY, type_)
        return key not in self.anno
