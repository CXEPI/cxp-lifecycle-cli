from cli.helpers.file import load_config
from pathlib import Path


def get_app_schemas():
    valid_exts = {".yaml", ".yml", ".json"}
    config = load_config()
    schemas_path = Path(config["core_services"]["openAPI"])
    return [
        str(file_path)
        for file_path in schemas_path.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in valid_exts
    ]
