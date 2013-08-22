# this is a package
import namespaces

def patch():
    # Apply patch to Plone, if we are on a version before
    # the fix of XXX was applied
    from Products.CMFPlone import events
   
    class DummyEvent(object):
        profile_id = None
        tool = None
    ev = DummyEvent()
    try:
        events.profileImportedEventHandler(ev)
    except AttributeError:
        from Products.CMFCore.utils import getToolByName

        def profileImportedEventHandler(event):
            """
            When a profile is imported with the keyword "latest", it needs to
            be reconfigured with the actual number.
            """
            profile_id = event.profile_id
            if profile_id is None:
                return
            profile_id = profile_id.replace('profile-', '')
            gs = event.tool
            qi = getToolByName(gs, 'portal_quickinstaller', None)
            if qi is None:
                # CMF-only site, or a test run.
                return
            installed_version = gs.getLastVersionForProfile(profile_id)
            if installed_version == (u'latest',):
                actual_version = qi.getLatestUpgradeStep(profile_id)
                gs.setLastVersionForProfile(profile_id, actual_version)
        events.profileImportedEventHandler = profileImportedEventHandler

patch()
