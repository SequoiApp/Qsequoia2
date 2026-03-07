
# Petite pop-up pour indiquer qu'une fonction n'est aps encore dispo

from qgis.PyQt.QtWidgets import QMessageBox

def unknown_function(parent=None):
    """
    Affiche une boîte de dialogue indiquant que la fonctionnalité n'est pas encore disponible.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle("Fonctionnalité non disponible")
    msg.setText("Cette fonctionnalité n'est pas encore disponible.")
    msg.setIcon(QMessageBox.Information)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()




