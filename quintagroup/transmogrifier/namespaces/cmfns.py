"""
    CMF Marshall namespace is overrided here in order to fix
    LocalRolesAttribute class. It's not working in Marshall Product.
"""

from Products.Marshall.namespaces import cmfns as base


class LocalRolesAttribute(base.LocalRolesAttribute):

    def getAttributeNames(self):
        return (self.name, 'security')
    
    def processXml(self, context, node):
        nsprefix = node.tag[:node.tag.find('}')+1]
        local_roles = node.findall(nsprefix+self.name)
        
        if len(local_roles) == 0:
            return

        data = context.getDataFor(self.namespace.xmlns)
        values = data.setdefault(self.name, [])
        
        for lrole in local_roles:
            values.append((lrole.get('user_id'), lrole.get('role')))
        
        return True

class WorkflowAttribute(base.WorkflowAttribute):
    
    def processXml(self, context, node):
        data = context.getDataFor(self.namespace.xmlns)
        wf_data = data.setdefault(self.name, {})
        nsprefix = node.tag[:node.tag.find('}')+1]

        for wf_node in node.findall(nsprefix+'workflow'):
            # workflow
            wf_id = wf_node.attrib.get(nsprefix+'id') or \
                    wf_node.attrib.get('id')
            if wf_id is None:
                continue

            # history
            wf = wf_data.setdefault(wf_id, [])
            hist_nodes = wf_node.findall(nsprefix+'history')
            for hist_node in hist_nodes:
                record = {}
                wf.append(record)

                #var
                var_nodes = hist_node.findall(nsprefix+'var')
                vid = vtype = value = None

                for var_node in var_nodes:
                    vid = var_node.attrib.get(nsprefix+'id') or \
                          var_node.attrib.get('id')
                    vtype = var_node.attrib.get(nsprefix+'type',None) or \
                            var_node.attrib.get('type')
                    value = var_node.attrib.get(nsprefix+'value',None) or \
                            var_node.attrib.get('value') or ''

                    if not (vid and vtype and value is not None):
                        continue

                    value = base.demarshall_value(value, vtype)
                    record[vid] = value

        return True

class CMF(base.CMF):
    
    attributes = (
        base.TypeAttribute('type'),
        WorkflowAttribute('workflow_history'),
        LocalRolesAttribute('local_role')
        )
