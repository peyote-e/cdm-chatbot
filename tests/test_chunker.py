from app.ingestion.chunker import build_chunk


# checks that the rich chunk really keeps the full attribute information
def test_build_chunk_includes_attribute_details():
    entity = {
        "entity_name": "Bank",
        "description": "A bank entity.",
        "extends_entity": "CdsStandard",
        "attributes": [
            {
                "name": "bankName",
                "display_name": "Bank Name",
                "type": "string",
                "description": "Name of the bank.",
                "enum_values": [],
                "referenced_entity": "",
                "is_relationship": False,
            },
            {
                "name": "statusCode",
                "display_name": "Status",
                "type": "listLookup",
                "description": "Bank status.",
                "enum_values": ["Active", "Inactive"],
                "referenced_entity": "",
                "is_relationship": False,
            },
        ],
        "relationships": [
            {
                "name": "homeBranchId",
                "type": "entityId",
                "display_name": "Home Branch",
                "referenced_entity": "Branch",
                "description": "Primary branch.",
                "enum_values": [],
                "is_relationship": True,
            }
        ],
    }

    chunk = build_chunk(entity)

    assert "Attributes (own):" in chunk
    assert '"name": "bankName"' in chunk
    assert '"type": "string"' in chunk
    assert '"display_name": "Bank Name"' in chunk
    assert '"description": "Name of the bank."' in chunk
    assert '"enum_values": ["Active", "Inactive"]' in chunk
    assert '"referenced_entity": ""' in chunk
    assert '"is_relationship": false' in chunk
    assert "Related entities (foreign keys):" in chunk
    assert '"name": "homeBranchId"' in chunk
    assert '"type": "entityId"' in chunk
    assert '"display_name": "Home Branch"' in chunk
    assert '"referenced_entity": "Branch"' in chunk
    assert '"is_relationship": true' in chunk


# checks that minimal mode still gives the old compact chunk style
def test_build_chunk_minimal_matches_old_style():
    entity = {
        "entity_name": "Bank",
        "description": "A bank entity.",
        "extends_entity": "CdsStandard",
        "attributes": [
            {
                "name": "bankName",
                "display_name": "Bank Name",
                "type": "string",
                "description": "Name of the bank.",
                "enum_values": [],
                "referenced_entity": "",
                "is_relationship": False,
            },
            {
                "name": "statusCode",
                "display_name": "Status",
                "type": "listLookup",
                "description": "Bank status.",
                "enum_values": ["Active", "Inactive"],
                "referenced_entity": "",
                "is_relationship": False,
            },
        ],
        "relationships": [
            {
                "name": "homeBranchId",
                "type": "entityId",
                "display_name": "Home Branch",
                "referenced_entity": "Branch",
                "description": "Primary branch.",
                "enum_values": [],
                "is_relationship": True,
            }
        ],
    }

    chunk = build_chunk(entity, attribute_detail="minimal")

    assert "Attributes (own): Bank Name (string), Status (listLookup)" in chunk
    assert "Enum attribute — Status: Active | Inactive" in chunk
    assert "Related entities (foreign keys): Branch (via homeBranchId)" in chunk
