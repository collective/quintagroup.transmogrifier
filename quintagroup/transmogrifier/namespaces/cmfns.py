"""
    CMF Marshall namespace is overrided here in order to fix
    LocalRolesAttribute class. It's not working in Marshall Product.
"""

from Products.Marshall.namespaces import cmfns as base


class LocalRolesAttribute(base.LocalRolesAttribute):

    
    def get(self, instance):
        """ overide local roles reader due to rare usecase of non-unicode strings in migrated Plone instances."""
        lr = getattr( instance, '__ac_local_roles__', {})
        for k in lr.keys():
            for i in range(len(lr[k])):
                lr[k][i] = lr[k][i].encode('utf-8')
        return lr


class CMF(base.CMF):
    
    attributes = (
        base.TypeAttribute('type'),
        base.WorkflowAttribute('workflow_history'),
        LocalRolesAttribute('local_role')
        )
