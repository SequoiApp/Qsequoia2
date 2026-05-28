from qgis.core import QgsExpression, QgsExpressionContext, QgsFeatureRequest, QgsExpressionContextUtils
from ..utils.seq_config import *
from qgis.PyQt.QtCore import QVariant
from collections import defaultdict


def seq_desc_fields() -> list:
    keys = [
        "std_type", "std_wealth", "std_stage", "std_year",
        "is_damaged", "is_available", "is_compartmented",
        "res_spe1", "res_spe2", "res_struct",
        "cop_spe1", "cop_spe2", "cop_density", "cop_nature",
        "reg_spe1", "reg_spe2", "reg_stage", "reg_density",
        "treatment",
        "is_subsidized", "subsidy",
        "comment", "station"
    ]

    return keys


def sspf_surface_calculation(ua_layer) -> str:
    selected = ua_layer.getSelectedFeatures()
    has_selected = ua_layer.selectedFeatureCount()
    all = ua_layer.getFeatures()
    features = selected if has_selected else all 
    area_ha = sum(f.geometry().area() for f in features) / 10000
    return f"{area_ha:.4f} ha"


def select_feats_by_expression(layer, expr, iface):

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



def build_mngnt_code(ua_layer, pf_field, sspf_field):
    groups = defaultdict(list)

    for feat in ua_layer.getFeatures():

        pf = feat[pf_field]
        sspf = feat[sspf_field]

        ug = f"{pf}.{sspf}"

        groups[ug].append(feat)
    
    return groups


def ua_check_ug(ua_layer, verbose=True) -> dict:

    pf_field = seq_field("pcl_code")["name"]
    sspf_field = seq_field("sub_code")["name"]

    desc_fields = []

    for key in seq_desc_fields():
        field = seq_field(key)["name"]
        desc_fields.append(field)


    groups = build_mngnt_code(ua_layer, pf_field, sspf_field)

    report = {}

    for ug, feats in groups.items():

        bad = {}

        for field in desc_fields:

            values = {

                str(f[field])

                for f in feats

                if f[field] not in (None, "")
            }

            if len(values) > 1:

                bad[field] = sorted(values)

        if bad:

            report[ug] = bad

    is_valid = len(report) == 0

    if not is_valid:

        messageLog(f"WARNING: {len(report)} inconsistent UG detected")

        for i, (ug, fields) in enumerate(report.items()):

            if i > 0:
                messageLog("-" * 50)

            messageLog(f"UG '{ug}' has inconsistent descriptive fields:")

            for field, vals in fields.items():

                vals_str = ", ".join(vals)

                messageLog(f"  - {field} contains multiple values: {vals_str}")

    elif verbose:

        messageLog("All UG are consistent.")

    return report

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