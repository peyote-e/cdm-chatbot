"""
parses enities into a normalised format (see example)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# CDM base types that have no CDM entity file we can parse further
_BASE_TYPES = {"CdsStandard", "CdmEntity", ""}


def _en_trait_value(traits: list, trait_ref: str) -> str:
    for trait in traits:
        if not isinstance(trait, dict):
            continue
        if trait.get("traitReference") != trait_ref:
            continue
        for arg in trait.get("arguments", []):
            if not isinstance(arg, dict):
                continue
            er = arg.get("entityReference", {})
            if not isinstance(er, dict):
                continue
            for row in er.get("constantValues", []):
                if isinstance(row, list) and len(row) >= 2 and row[0] == "en":
                    return row[1]
    return ""


def _description_from_traits(traits: list) -> str:
    return _en_trait_value(traits, "is.localized.describedAs")


def _display_name_from_traits(traits: list) -> str:
    return _en_trait_value(traits, "is.localized.displayedAs")


def _parse_data_type(data_type: Any) -> str:
    if isinstance(data_type, str):
        return data_type
    if isinstance(data_type, dict):
        return data_type.get("dataTypeReference", "unknown")
    return "unknown"


def _enum_values(data_type: Any) -> list[str]:
    if not isinstance(data_type, dict):
        return []
    if data_type.get("dataTypeReference") != "listLookup":
        return []
    for trait in data_type.get("appliedTraits", []):
        if not isinstance(trait, dict):
            continue
        if trait.get("traitReference") != "does.haveDefault":
            continue
        for arg in trait.get("arguments", []):
            if not isinstance(arg, dict):
                continue
            er = arg.get("entityReference", {})
            if isinstance(er, dict) and er.get("entityShape") == "listLookupValues":
                return [
                    row[1]
                    for row in er.get("constantValues", [])
                    if isinstance(row, list) and len(row) >= 2
                ]
    return []


def _parse_member(member: dict) -> dict | None:
    """Parse one attribute member into a normalised dict."""
    if not isinstance(member, dict):
        return None

    # Entity-reference attribute (a relationship / foreign key)
    if "entity" in member:
        entity_info = member["entity"]
        if isinstance(entity_info, dict):
            ref = entity_info.get("entityReference", "")
            if isinstance(ref, dict):
                ref = ref.get("entityName", "")
        else:
            ref = str(entity_info)

        res = member.get("resolutionGuidance", {})
        fk = res.get("entityByReference", {}).get("foreignKeyAttribute", {}) if res else {}
        fk_name = fk.get("name", member.get("name", "")) if fk else member.get("name", "")

        return {
            "name": fk_name,
            "type": "entityId",
            "display_name": (fk.get("displayName") or member.get("name", "")) if fk else member.get("name", ""),
            "description": (fk.get("description", "") if fk else ""),
            "enum_values": [],
            "referenced_entity": ref,
            "is_relationship": True,
        }

    if "name" not in member:
        return None

    name = member["name"]
    traits = member.get("appliedTraits", [])
    data_type = member.get("dataType", "string")

    return {
        "name": name,
        "type": _parse_data_type(data_type),
        "display_name": member.get("displayName") or _display_name_from_traits(traits) or name,
        "description": member.get("description") or _description_from_traits(traits),
        "enum_values": _enum_values(data_type),
        "referenced_entity": "",
        "is_relationship": False,
    }


def _extends_entity_name(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        ref = raw.get("entityReference", "")
        if isinstance(ref, dict):
            return ref.get("entityName", "")
        return ref
    return ""


def parse_entity_file(file_path: Path) -> dict | None:
    """Parse a .cdm.json entity file. Returns None if the file is not an entity."""
    try:
        with open(file_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    definitions = data.get("definitions", [])
    if not definitions:
        return None

    entity_def = definitions[0]
    entity_name = entity_def.get("entityName", "")
    if not entity_name:
        return None

    # Description: prefer field, fall back to exhibitsTraits
    description = entity_def.get("description", "")
    if not description:
        description = _description_from_traits(entity_def.get("exhibitsTraits", []))

    extends = _extends_entity_name(entity_def.get("extendsEntity", ""))

    attributes: list[dict] = []
    relationships: list[dict] = []

    for has_attr in entity_def.get("hasAttributes", []):
        if isinstance(has_attr, str):
            continue
        if not isinstance(has_attr, dict):
            continue

        # Most banking entities wrap attrs in attributeGroupReference.members
        if "attributeGroupReference" in has_attr:
            group = has_attr["attributeGroupReference"]
            if isinstance(group, dict):
                for member in group.get("members", []):
                    parsed = _parse_member(member)
                    if parsed:
                        (relationships if parsed["is_relationship"] else attributes).append(parsed)
        else:
            parsed = _parse_member(has_attr)
            if parsed:
                (relationships if parsed["is_relationship"] else attributes).append(parsed)

    return {
        "entity_name": entity_name,
        "description": description,
        "extends_entity": extends,
        "attributes": attributes,
        "relationships": relationships,
        "source_path": str(file_path),
    }


def parse_manifest(manifest_data: dict) -> dict:
    """Extract entity list and relationships from a manifest dict."""
    entities = []
    for entry in manifest_data.get("entities", []):
        path = entry.get("entityPath", "")
        filename = path.split("/")[0] if "/" in path else path
        name = path.split("/")[-1] if "/" in path else filename.replace(".cdm.json", "")
        entities.append({"name": name, "filename": filename})

    relationships = []
    for rel in manifest_data.get("relationships", []):
        from_path = rel.get("fromEntity", "")
        to_path = rel.get("toEntity", "")

        from_entity = from_path.split("/")[0].replace(".cdm.json", "") if from_path else ""
        # to_path may be "/core/.../User.cdm.json/User" — last segment is entity name
        to_parts = to_path.split("/")
        to_entity = to_parts[-1] if to_parts else ""
        if not to_entity or "." in to_entity:
            to_entity = to_parts[-2].replace(".cdm.json", "") if len(to_parts) >= 2 else ""

        from_attr = rel.get("fromEntityAttribute", "")
        to_attr = rel.get("toEntityAttribute", "")

        if from_entity and to_entity and from_attr:
            relationships.append({
                "from_entity": from_entity,
                "from_attribute": from_attr,
                "to_entity": to_entity,
                "to_attribute": to_attr,
            })

    return {"entities": entities, "relationships": relationships}
