import processing
import math
from qgis.core import QgsProcessing

def buffer(layer, distance, dissolve = True, segments=8):
    buffered = processing.run("native:buffer", {
        "INPUT": layer,
        "DISTANCE": distance,
        "SEGMENTS": segments,
        "DISSOLVE": dissolve,
        "OUTPUT": "memory:"
        })["OUTPUT"]
    
    return buffered

def multipart_to_singleparts(layer):
    singleparts = processing.run("native:multiparttosingleparts", {
        "INPUT": layer,
        "OUTPUT": "memory:"
        })["OUTPUT"]
    return singleparts
