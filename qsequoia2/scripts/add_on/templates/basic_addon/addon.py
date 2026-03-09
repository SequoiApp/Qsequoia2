""""""


from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout


class {{ADDON_CLASS}}:

    def __init__(self, iface, project_name, style_folder, downloads_path, project_folder):

        self.iface = iface
        self.project_name = project_name
        self.style_folder = style_folder
        self.downloads_path = downloads_path
        self.project_folder = project_folder


    def get_name(self):
        return "{{ADDON_NAME}}"


    def get_tab(self):

        widget = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Addon {{ADDON_NAME}} chargé")

        layout.addWidget(label)
        widget.setLayout(layout)

        return widget