
from qgis.core import Qgis

def test(self,iface,args):
    # message QGIS
    self.iface.messageBar().pushMessage(" test d'appel fonction QSequoia2",args,level=Qgis.Success,duration=5)

