# -*- coding: utf-8 -*-
from zope.component import getMultiAdapter, getUtilitiesFor
from filecmp import dircmp
from tarfile import TarFile
from unittest import defaultTestLoader
from plone.portlets.interfaces import IPortletRetriever
from plone.app.portlets.portlets.navigation import INavigationPortlet
from plone.portlets.interfaces import IPortletManager

from quintagroup.transmogrifier.tests.base import TransmogrifierTestCase


class SetupTests(TransmogrifierTestCase):

    def testTransmogrifierInstalled(self):
        # a simple sanity check whether the profile we're testing
        # is actually installed in our fixture
        portal_setup = self.portal.portal_setup
        self.failUnless(u'quintagroup.transmogrifier:default' in
            [info['id'] for info in  portal_setup.listProfileInfo()]
        )


class RoundtrippingTests(TransmogrifierTestCase):
    """ These tests export content, re-import it and make sure
        that we get what we expect.
    """

    def export_site(self, source=None):
        if source is None:
            source = self.portal
        setup = source.portal_setup
        result = setup._doRunExportSteps(['content_quinta'])
        tgz_filename = "%s/%s" % (self.tempfolder, result['filename'])
        tgz = open(tgz_filename, 'w')
        tgz.write(result['tarball'])
        tgz.close()
        return tgz_filename

    def import_site(self, filename, target=None):
        if target is None:
            target = self.target

        try:
            from zope.site.hooks import setSite
        except ImportError:
            from zope.app.component.hooks import setSite

        setSite(target)
        setup = target.portal_setup
        tarball = open(filename)
        setup.runAllImportStepsFromProfile(None, True, archive=tarball.read())

    def recursive_comparison(self, comparison):
        report = {
            'diff_files' : comparison.diff_files,
            'funny_files' : comparison.funny_files
        }
        for sd in comparison.subdirs.itervalues():
            report.update(self.recursive_comparison(sd))
        return report
    def prepare_navigation(self):
        """
        Before we start to export plone 3.x site content we
        need to select some folder as root of navigation in
        navigation portlet. This must be done, otherwise
        then trying to import portlet navigation with empty
        root field - we'll get validation error.

        """

        # let's create folders that will be our navigation root
        for p in [self.portal, self.target]:
            getattr(p, 'invokeFactory')('Folder', 'navigation_root')

        for name, portletManager in getUtilitiesFor(IPortletManager):
            retriever = getMultiAdapter((self.portal, portletManager),
                                         IPortletRetriever)
            navigation_assignments = [portlet['assignment']
                for portlet in retriever.getPortlets()
                if INavigationPortlet.providedBy(portlet['assignment'])]

            for na in navigation_assignments:
                setattr(na, 'root', '/navigation_root')

    def testTripWireExport(self):
        """ A basic sanity check. We create demo data, normalize it, export it
            and then recursively compare its file structure with a previous
            snapshot of that export (which has been added to the test fixture.

            This enables us to detect changes in the marshalling. If this test
            begins to fail, we should simply commit the new structure to the
            fixture (after anyalyzing the differences) to make the test pass
            again.
        """
        # normalize uid, creation and modifcation dates to enable meaningful
        # diffs
        self.loginAsPortalOwner()
        for brain in self.portal.portal_catalog():
            obj = brain.getObject()
            obj.setModificationDate('2010-01-01T14:00:00Z')
            obj.setCreationDate('2010-01-01T14:00:00Z')
            obj._at_uid = brain.getPath()

        # monkeypatch the CMF marshaller to exclude the workflow history
        # as that information is difficult to normalize
        from quintagroup.transmogrifier.namespaces.cmfns import CMF
        CMF.attributes = (CMF.attributes[0], CMF.attributes[2])

        # perform the actual export
        exported = TarFile.open(self.export_site(), 'r:gz')
        exported_structure_path = '%s/exported/' % self.tempfolder
        for member in exported.getmembers():
            exported.extract(member, path=exported_structure_path)
        pversion = self.getPloneVersion()
        snapshot_structure_path = '%s/reference_export/%s/' % \
            (self.data_path, '_'.join(map(str, pversion[:3])))
        comparison = dircmp(snapshot_structure_path, exported_structure_path)

        # for the test we check that there are no files that differ
        # and that all files were comparable (funny_files)
        report = self.recursive_comparison(comparison)
        self.assertEqual(report['diff_files'], [])
        self.assertEqual(report['funny_files'], [])

    def testRoundTrip(self):
        """ export the demo data and import it into the target site,
            paying particular attention to events and to the mimetype
            of text fields, as these were observed bugs in TTW testing.
        """

        # make sure, that prior to import, the target size does not
        # have the same number of events:
        self.loginAsPortalOwner()
        self.failIf(sorted(list(self.portal.events.objectIds())) ==
            sorted(list(self.target.events.objectIds())))

        self.assertEqual(self.target['front-page'].getRelatedItems(), [])
        self.portal['front-page'].setRelatedItems([self.portal.events.party,
            self.portal.news['hold-the-press']])
        source_related = sorted(['/'.join(obj.getPhysicalPath()) for obj in self.portal['front-page'].getRelatedItems()])
        self.assertEqual(source_related,
            ['/plone/events/party', '/plone/news/hold-the-press'])

        if self.getPloneVersion()[0] < 4:
            # we need to do some preparation before site export
            self.prepare_navigation()

        # export the source site and import it into the target:
        self.import_site(self.export_site())

        # now, we have the same number of events
        self.assertEqual(sorted(list(self.portal.events.objectIds())),
            sorted(list(self.target.events.objectIds())))

        # the imported event has the identical startDate as its source:
        self.assertEqual(self.portal.events.party.startDate,
            self.target.events.party.startDate)

        # the front page body text is text/html, right?
        frontpage = self.target['front-page']
        self.assertEqual(frontpage.getField('text', frontpage).getContentType(frontpage),
            'text/html')

        # revisit the related items
        target_related = sorted(['/'.join(obj.getPhysicalPath()) for obj in self.target['front-page'].getRelatedItems()])
        self.assertEqual(target_related,
            ['/target/events/party', '/target/news/hold-the-press'])

def test_suite():
    return defaultTestLoader.loadTestsFromName(__name__)

