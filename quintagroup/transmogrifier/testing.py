# -*- coding: utf-8 -*-
from Testing.ZopeTestCase import installPackage
from Products.Five import zcml
from Products.Five import fiveconfigure
from collective.testcaselayer.ptc import BasePTCLayer, ptc_layer
from Products.PloneTestCase import ptc


class TransmogrifierLayer(BasePTCLayer):
    """ layer for integration tests """

    ptc.setupPloneSite(id="target")

    def afterSetUp(self):
        fiveconfigure.debug_mode = True
        from quintagroup import transmogrifier
        zcml.load_config('testing.zcml', transmogrifier)
        fiveconfigure.debug_mode = False
        installPackage('quintagroup.transmogrifier', quiet=True)
        self.addProfile('quintagroup.transmogrifier:default')
        self.createDemoContent()

    def createDemoContent(self):
        self.loginAsPortalOwner()
        self.portal.news.invokeFactory('News Item', id='hold-the-press', title=u"Høld the Press!")
        self.portal.events.invokeFactory('Event',
            id='party',
            title=u"Süper Pärty",
            startDate='2010/01/01 15:00:00',
            endDate='2010/01/01 15:00:00')


transmogrifier = TransmogrifierLayer(bases=[ptc_layer])
