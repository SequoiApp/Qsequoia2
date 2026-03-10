# exemple d'appel d'une fonction Qsequoia2 depuis un script externe
from qgis.core import *

# Appel d'une fonction QSEQUOIA2

def PluginExemple(pf, self, iface, args):
    pf.test(self, iface, args)

# Appel d'une fonction interne à l'addon 
def AddonExemple(self, iface, args):
    self.iface.messageBar().pushMessage(" test d'appel fonction addon",args,level=Qgis.Success,duration=5)
