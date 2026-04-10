from pathlib import Path
import platform
import winreg

def get_download_folder():
    """recherche le dossier de telechargement de l'utilisateur pour watchdog"""
    system = platform.system()

    # Windows : lecture du registre (si l’utilisateur a déplacé le dossier)
    if system == "Windows":
        try:
            sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                downloads, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
                return Path(downloads)
        except:
            return Path.home() / "Downloads"

    # macOS et Linux
    return Path.home() / "Downloads"