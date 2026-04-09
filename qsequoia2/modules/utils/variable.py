from typing import Any

from qgis.core import QgsProject,QgsExpressionContextUtils

# ------------------------------------------------------------------------------

# Utility functions to get/set QGIS expression variables

# Author: Matthieu Chevereau, Paul Carteron

# Modified by: Alexandre Le Bars

# ------------------------------------------------------------------------------



def get_global_variable(name: str) -> Any:
    """Return the value of a *global* expression variable."""
    return QgsExpressionContextUtils.globalScope().variable(name)

def set_global_variable(name: str, value: Any) -> None:
    """Set a global expression variable (string/int/float/bool)."""
    QgsExpressionContextUtils.setGlobalVariable(name, value)
    return None

def get_project_variable(name: str) -> Any:
    """Return a project-level variable or `None` if missing."""
    return QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable(name)

def set_project_variable(name: str, value: Any) -> None:
    """
    Set a project-level variable.

    Anything that isn’t str/int/float/bool is auto-converted to str to avoid
    QVariant type errors.
    """
    _safe_set(QgsExpressionContextUtils.setProjectVariable, name, value)

def _safe_set(setter, name: str, value: Any) -> None:
    if not isinstance(value, (str, int, float, bool)):
        print(f"[Warn] {name!r}: {type(value).__name__} → str")
        value = str(value)
    try:
        # setter signature: (project, name, value) OR (name, value) for global
        setter(QgsProject.instance(), name, value)  # *ignored* by global setter
    except Exception as err:
        print(f"[Error] cannot set {name!r}: {value!r}  →  {err}")


