"""
Builds a text chunk for each parsed CDM entity.

The chunk keeps the entity-level summary readable, but renders attributes
close to the parser's normalised shape so attribute-centric questions such as
"what is bankId?" have the needed fields in vector-retrieved context.
"""

from __future__ import annotations

from typing import Literal

_BASE_TYPES = {"CdsStandard", "CdmEntity", ""}
AttributeDetail = Literal["minimal", "full"]


def _format_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_attribute_block(attribute: dict) -> list[str]:
    return [
        "  {",
        f'    "name": "{attribute.get("name", "")}",',
        f'    "type": "{attribute.get("type", "")}",',
        f'    "display_name": "{attribute.get("display_name", "")}",',
        f'    "description": "{attribute.get("description", "")}",',
        f'    "enum_values": {_format_list(attribute.get("enum_values", []))},',
        f'    "referenced_entity": "{attribute.get("referenced_entity", "")}",',
        f'    "is_relationship": {_format_bool(attribute.get("is_relationship", False))}',
        "  }",
    ]


def _format_minimal_attribute_line(attribute: dict) -> str:
    type_str = attribute.get("type", "")
    name = attribute.get("display_name") or attribute.get("name", "")
    return f"{name} ({type_str})" if type_str else name


def build_chunk(entity: dict, attribute_detail: AttributeDetail = "full") -> str:
    lines: list[str] = []

    lines.append(f"Entity: {entity['entity_name']}")

    desc = entity.get("description", "").strip()
    if desc:
        lines.append(f"Description: {desc}")

    extends = entity.get("extends_entity", "").strip()
    if extends and extends not in _BASE_TYPES:
        lines.append(f"Inherits from: {extends}")

    # Own attributes
    attrs = entity.get("attributes", [])
    if attrs:
        if attribute_detail == "minimal":
            attr_parts = [_format_minimal_attribute_line(a) for a in attrs]
            enum_lines: list[str] = []
            lines.append(f"Attributes (own): {', '.join(attr_parts)}")
            for a in attrs:
                display_name = a.get("display_name") or a.get("name", "")
                if a.get("enum_values"):
                    enum_lines.append(
                        f"Enum attribute — {display_name}: {' | '.join(a['enum_values'])}"
                    )
            lines.extend(enum_lines)
        else:
            lines.append("Attributes (own):")
            for a in attrs:
                lines.extend(_format_attribute_block(a))

    # Relationship / foreign-key attributes
    rels = entity.get("relationships", [])
    if rels:
        if attribute_detail == "minimal":
            rel_parts: list[str] = []
            for r in rels:
                ref = r.get("referenced_entity", "")
                via = r.get("name", "")
                if ref:
                    rel_parts.append(f"{ref} (via {via})" if via else ref)
            if rel_parts:
                lines.append(f"Related entities (foreign keys): {', '.join(rel_parts)}")
        else:
            lines.append("Related entities (foreign keys):")
            for r in rels:
                lines.extend(_format_attribute_block(r))

    return "\n".join(lines)


def build_chunks(
    entities: list[dict], attribute_detail: AttributeDetail = "full"
) -> list[dict]:
    """Return list of {entity_name, chunk, metadata} dicts ready for embedding."""
    result = []
    for entity in entities:
        chunk = build_chunk(entity, attribute_detail=attribute_detail)
        result.append({
            "entity_name": entity["entity_name"],
            "chunk": chunk,
            "metadata": {
                "entity_name": entity["entity_name"],
                "extends_entity": entity.get("extends_entity", ""),
                "type": "entity",
            },
        })
    return result
