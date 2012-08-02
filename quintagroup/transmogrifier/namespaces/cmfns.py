"""
    CMF Marshall namespace is overrided here in order to fix
    LocalRolesAttribute class. It's not working in Marshall Product.
"""

from Products.Marshall.namespaces import cmfns as base


class LocalRolesAttribute(base.LocalRolesAttribute):

    
    def deserialize(self, instance, ns_data):
        values = ns_data.get(self.field_id)
        if not values:
            return
        for user_id, role in values:
            instance.manage_addLocalRoles(user_id, [role])


    def processXml(self, context, node):
        nsprefix = node.tag[:node.tag.find('}')+1]
        local_roles = node.findall(nsprefix+self.field_id)
        
        if len(local_roles) == 0:
            return

        data = context.getDataFor(self.namespace.xmlns)
        values = data.setdefault(self.field_id, [])
        
        for lrole in local_roles:
            values.append((lrole.get('user_id'), lrole.get('role')))
        
        return True

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
        LocalRolesAttribute('security','local_role'),
        )
