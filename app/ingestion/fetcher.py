"""
Reads the Bank parts from CDM saved locally (currnt version, no old versions), if it cant find it will give error and instructions
"""

import json
from pathlib import Path

from app.config import settings

BANKING_REL_PATH = (
    "core/applicationCommon/foundationCommon/crmCommon"
    "/accelerators/financialServices/banking"
)
MANIFEST_FILENAME = "banking.manifest.cdm.json"

_MISSING_DATA_MSG = (
    "CDM data not found at '{path}'.\n"
    "Clone the Microsoft CDM repo with a sparse checkout:\n\n"
    "    git clone --filter=blob:none --sparse https://github.com/microsoft/CDM.git\n"
    "    cd CDM\n"
    "    git sparse-checkout set schemaDocuments/core/applicationCommon\n\n"
    "Then set CDM_LOCAL_PATH=<path-to-CDM>/schemaDocuments in your .env file."
)


def _schema_root() -> Path:
    p = Path(settings.cdm_local_path)
    if not p.is_absolute():
        # Resolve relative to the repo root (two levels above app/)
        p = (Path(__file__).parent.parent.parent / settings.cdm_local_path).resolve()
    if not p.exists():
        raise FileNotFoundError(_MISSING_DATA_MSG.format(path=p))
    return p


def load_json(relative_to_schema_docs: str) -> dict:
    """Load a CDM JSON file by its path relative to schemaDocuments/."""
    path = _schema_root() / relative_to_schema_docs
    if not path.exists():
        raise FileNotFoundError(_MISSING_DATA_MSG.format(path=path))
    with open(path) as f:
        return json.load(f)


def load_manifest() -> dict:
    return load_json(f"{BANKING_REL_PATH}/{MANIFEST_FILENAME}")


def load_entity(filename: str) -> dict | None:
    """Load a single entity file from the banking folder. Returns None if missing."""
    try:
        return load_json(f"{BANKING_REL_PATH}/{filename}")
    except FileNotFoundError:
        return None


def list_entity_filenames(manifest: dict) -> list[str]:
    """Return unversioned .cdm.json filenames referenced in the manifest."""
    seen: set[str] = set()
    filenames: list[str] = []
    for entry in manifest.get("entities", []):
        path = entry.get("entityPath", "")
        filename = path.split("/")[0] if "/" in path else path
        if not filename or filename == MANIFEST_FILENAME or filename in seen:
            continue
        # Skip versioned files e.g. Bank.1.3.cdm.json — second segment is a digit
        if not filename.split(".")[1].isdigit():
            seen.add(filename)
            filenames.append(filename)
    return filenames
