from .variable import *
from .Qmessage import * 

def update_plugin(iface,parent):
    """force plugin to reload the data in seq_dir and qgis project"""
    seq_dir = get_project_variable("QS2_seq_dir")
    

    if seq_dir:
        self._select_project(seq_dir)
        messageBar(iface, f"{seq_dirname}")




