#! -*- coding: utf-8 -*-
from quintagroup.transmogrifier.tests.base import TransmogrifierTestCase
from quintagroup.transmogrifier.namespaces.cmfns import safe_utf8
from quintagroup.transmogrifier.namespaces.cmfns import LocalRolesAttribute
from quintagroup.transmogrifier.namespaces.cmfns import WorkflowAttribute

from DateTime import DateTime


class CmfNsTestCase(TransmogrifierTestCase):

    def test_safe_utf8(self):
        self.assertEqual(safe_utf8(None), None)
        self.assertEqual(safe_utf8(''), '')
        self.assertEqual(safe_utf8(u'ö'), '\xc3\xb6')
        self.assertEqual(safe_utf8('\xc3\xb6'), '\xc3\xb6')
        self.assertEqual(safe_utf8(12), 12)

    def test_workflow_history(self):
        workflow_history = {'fhnw_plone_workflow': (
            {'action': None, 'review_state': 'private',
             'actor': u'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:10.856988 GMT+2')},
            {'action': 'publish_web', 'review_state': 'published_web',
             'actor': u'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:18.625354 GMT+2')},
            {'action': 'hide', 'review_state': 'private',
             'actor': u'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:49.015124 GMT+2')})}
        self.folder.invokeFactory('Document', 'doc1')
        doc1 = self.folder['doc1']
        setattr(doc1, 'workflow_history', workflow_history)
        wa = WorkflowAttribute('workflow_history')
        self.assertEqual(wa.get(doc1), {'fhnw_plone_workflow': (
            {'action': None, 'review_state': 'private',
             'actor': 'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:10.856988 GMT+2')},
            {'action': 'publish_web', 'review_state': 'published_web',
             'actor': 'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:18.625354 GMT+2')},
            {'action': 'hide', 'review_state': 'private',
             'actor': 'fred.flintstone', 'comments': '',
             'time': DateTime('2012/05/11 11:51:49.015124 GMT+2')})})
           
    def test_local_roles(self):
        local_roles = {u'fred.flintstone': ['Owner']}
        #self.setRoles(['Manager']) 
        self.folder.invokeFactory('Document', 'doc1')
        doc1 = self.folder['doc1']
        setattr(doc1, '__ac_local_roles__', local_roles)
        lra = LocalRolesAttribute('local_roles')
        self.assertEqual(lra.get(doc1), {'fred.flintstone': ['Owner']})
