import re

def update_forest_name(prefix, seq_identifier):
    """Met à jour le nom de la forêt en combinant le nom du projet et le type de propriété sélectionné."""

    base = seq_identifier

    base = re.sub(r"^(ST|STE|SAINT)(.*)", r"\1 \2", base, flags=re.IGNORECASE)

    base = (base.lower().replace("_", " ").replace(".", " ").replace("-", " ").title().split())
    co = ["De", "La", "D", "Le"]
    ST = ["ST", "STE", "SAINT"]
    base = [elem.title() if elem in ST else elem for elem in base]

    base = [elem.lower() if elem in co else elem for elem in base]
    base = " ".join(base)
    
    if prefix and base:
        # plural names take " des "
        if base.lower().endswith("s"):
            connector = " des "
        # then vowel or mute-h → d'
        elif base[0].lower() in ("a","e","i","o","u","h"):
            connector = " d'"
        # otherwise normal " de "
        else:
            connector = " de "
        forest_name = f"{prefix}{connector}{base}"
    else:
        forest_name = base
    
    return forest_name
