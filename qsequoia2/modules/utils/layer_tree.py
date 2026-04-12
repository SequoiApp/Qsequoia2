from qgis.core import QgsProject


def get_group(name: str, project=None):
    """
    Return an existing group or create it if missing.
    """
    project = project or QgsProject.instance()
    root = project.layerTreeRoot()

    name = str(name).strip().upper()
    group = root.findGroup(name)

    return group or root.addGroup(name)