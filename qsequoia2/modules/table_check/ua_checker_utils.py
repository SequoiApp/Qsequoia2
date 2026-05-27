from qgis.core import *
from ..utils.seq_config import *
from ..utils.alias import get_alias
from qgis.PyQt.QtCore import QVariant

def map_seq_layer_loader(key: str) -> QgsVectorLayer :
    layer = QgsProject.instance().mapLayersByName(get_alias(key))
    if not layer:
        return None
    return layer[0]

def sspf_surface_calculation(ua_layer) -> str:

    feats = list(ua_layer.getSelectedFeatures())
    if not feats: 
        surf = sum(f.geometry().area() for f in ua_layer.getFeatures()) / 10000
        return f"{round(surf,4)} ha"
    tmp = QgsVectorLayer("Polygon?crs=" + ua_layer.crs().authid(), "tmp", "memory")
    tmp.dataProvider().addFeatures(feats)
    surf = sum(f.geometry().area() for f in tmp.getFeatures()) / 10000
    return f"{round(surf,4)} ha"


def selectFeaturesByExpression(layer, expr, iface):

    exp = QgsExpression(expr)
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    request = QgsFeatureRequest(exp, context)

    ids = [f.id() for f in layer.getFeatures(request)]

    iface.layerTreeView().setCurrentLayer(layer)

    layer.removeSelection()
    layer.selectByIds(ids)

    iface.mapCanvas().zoomToSelected(layer)
    iface.mapCanvas().refresh()

    return ids

def get_pf_list(ua_layer, by_selc_feats = None) -> list:
    """return the list of all pf name (str)"""

    field = seq_field("pcl_code")["name"]
    if by_selc_feats:

        values = {f[field] for f in ua_layer.selectedFeatures()}
    else:
    
        values = ua_layer.uniqueValues(ua_layer.fields().indexOf(field))
    

    return [v for v in values]


def get_sspf_list(ua_layer, pf_list=None, by_selc_feats = None) -> list :
    """return the list of sspf by pf, if pf_list is None return all sspf of the layer"""
    
    sspf_field = seq_field("sub_code")["name"]
    pf_field = seq_field("pcl_code")["name"]
    
    if pf_list is None:
        pf_list = get_pf_list(ua_layer)

    if isinstance(pf_list, (str, QVariant)):
        pf_list = [pf_list]

    sspf_list = []

    for pf in pf_list:
        if by_selc_feats :
            sub_values = {f[sspf_field]for f in ua_layer.selectedFeatures()if str(f[pf_field]) == pf}            
        else :
            sub_values = {f[sspf_field]for f in ua_layer.getFeatures()if str(f[pf_field]) == pf}
        
        for d in sub_values:
            sspf_list.append(d)
            
    return sspf_list


def get_feats(ua_layer, field: str, pf: str, sspf: str) -> list:
    """Retourne les valeurs du champ pour une sous-parcelle PF/SSPF."""
    sspf_field = seq_field("sub_code")["name"]
    pf_field = seq_field("pcl_code")["name"]

    # Vérification du champ
    if field not in [f.name() for f in ua_layer.fields()]:
        return []

    expr = f"\"{pf_field}\" = '{pf}' AND \"{sspf_field}\" = '{sspf}'"

    feats_list = []
    for feat in ua_layer.getFeatures(QgsFeatureRequest().setFilterExpression(expr)):
        feats_list.append(feat[field])

    return feats_list



def check_values(feats_list) -> bool:
    checked_feats =  len(set(feats_list)) == 1
    if checked_feats == True:
        return checked_feats, [feats_list[0]]
    
    return checked_feats, list(set(feats_list))

    







    

