# -*- coding: utf-8 -*-
from filecmp import dircmp
from tarfile import TarFile
from unittest import defaultTestLoader
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
        snapshot_structure_path = '%s/reference_export/' % self.data_path
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
        self.failIf(sorted(list(self.portal.events.objectIds())) ==
            sorted(list(self.target.events.objectIds())))

        self.assertEqual(self.target['front-page'].getRelatedItems(), [])
        self.portal['front-page'].setRelatedItems([self.portal.events.party,
            self.portal.news['hold-the-press']])
        source_related = sorted(['/'.join(obj.getPhysicalPath()) for obj in self.portal['front-page'].getRelatedItems()])
        self.assertEqual(source_related,
            ['/plone/events/party', '/plone/news/hold-the-press'])

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

