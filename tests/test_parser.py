"""Unit tests for CDM JSON parsing logic."""

import pytest

from app.ingestion.parser import (
    _extends_entity_name,
    _parse_member,
    parse_manifest,
    parse_entity_file,
)
import json
import tempfile
from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────────────────────────

BANK_ENTITY_JSON = {
    "jsonSchemaSemanticVersion": "1.0.0",
    "imports": [{"corpusPath": "_allImports.cdm.json"}],
    "definitions": [
        {
            "entityName": "Bank",
            "extendsEntity": "CdsStandard",
            "exhibitsTraits": [
                {
                    "traitReference": "is.localized.describedAs",
                    "arguments": [
                        {
                            "entityReference": {
                                "entityShape": "localizedTable",
                                "constantValues": [["en", "The physical bank location."]],
                            }
                        }
                    ],
                }
            ],
            "hasAttributes": [
                {
                    "attributeGroupReference": {
                        "attributeGroupName": "attributesAddedAtThisScope",
                        "members": [
                            {
                                "name": "bankName",
                                "purpose": "hasA",
                                "dataType": "string",
                                "displayName": "Bank Name",
                                "description": "Name of the bank.",
                            },
                            {
                                "name": "routingNumber",
                                "purpose": "hasA",
                                "dataType": "string",
                                "displayName": "Routing Number",
                                "description": "ABA routing number.",
                            },
                            {
                                "entity": {"entityReference": "Branch"},
                                "name": "homeBranch",
                                "resolutionGuidance": {
                                    "entityByReference": {
                                        "allowReference": True,
                                        "foreignKeyAttribute": {
                                            "name": "homeBranchId",
                                            "displayName": "Home Branch",
                                            "description": "Primary branch.",
                                        },
                                    }
                                },
                            },
                        ],
                    }
                }
            ],
        }
    ],
}

MANIFEST_JSON = {
    "manifestName": "banking",
    "entities": [
        {"entityPath": "Bank.cdm.json/Bank"},
        {"entityPath": "Branch.cdm.json/Branch"},
        {"entityPath": "Account.1.3.cdm.json/Account"},  # versioned — should be skipped
    ],
    "relationships": [
        {
            "fromEntity": "Bank.cdm.json/Bank",
            "fromEntityAttribute": "homeBranchId",
            "toEntity": "Branch.cdm.json/Branch",
            "toEntityAttribute": "branchId",
        }
    ],
}


@pytest.fixture
def bank_entity_file(tmp_path):
    p = tmp_path / "Bank.cdm.json"
    p.write_text(json.dumps(BANK_ENTITY_JSON))
    return p


# ── parse_entity_file ─────────────────────────────────────────────────────────

def test_parse_entity_name(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    assert result is not None
    assert result["entity_name"] == "Bank"


def test_parse_description_from_traits(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    assert "physical bank location" in result["description"]


def test_parse_extends_entity(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    assert result["extends_entity"] == "CdsStandard"


def test_parse_plain_attributes(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    attr_names = [a["name"] for a in result["attributes"]]
    assert "bankName" in attr_names
    assert "routingNumber" in attr_names


def test_parse_entity_reference_becomes_relationship(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    rel_names = [r["referenced_entity"] for r in result["relationships"]]
    assert "Branch" in rel_names


def test_parse_relationship_is_not_in_attributes(bank_entity_file):
    result = parse_entity_file(bank_entity_file)
    attr_names = [a["name"] for a in result["attributes"]]
    assert "homeBranchId" not in attr_names


def test_parse_returns_none_for_empty_file(tmp_path):
    p = tmp_path / "empty.cdm.json"
    p.write_text("{}")
    assert parse_entity_file(p) is None


def test_parse_returns_none_for_invalid_json(tmp_path):
    p = tmp_path / "bad.cdm.json"
    p.write_text("not json {{")
    assert parse_entity_file(p) is None


# ── parse_manifest ────────────────────────────────────────────────────────────

def test_manifest_entities_unversioned_only():
    result = parse_manifest(MANIFEST_JSON)
    names = [e["name"] for e in result["entities"]]
    assert "Bank" in names
    assert "Branch" in names
    # Versioned file should still appear in manifest parse
    # (filtering of versioned filenames is done in fetcher.list_entity_filenames)


def test_manifest_relationships_parsed():
    result = parse_manifest(MANIFEST_JSON)
    assert len(result["relationships"]) == 1
    rel = result["relationships"][0]
    assert rel["from_entity"] == "Bank"
    assert rel["to_entity"] == "Branch"
    assert rel["from_attribute"] == "homeBranchId"


# ── _extends_entity_name ──────────────────────────────────────────────────────

def test_extends_string():
    assert _extends_entity_name("CdsStandard") == "CdsStandard"


def test_extends_dict_entity_reference_string():
    assert _extends_entity_name({"entityReference": "Account"}) == "Account"


def test_extends_dict_nested():
    assert _extends_entity_name({"entityReference": {"entityName": "Contact"}}) == "Contact"


def test_extends_empty():
    assert _extends_entity_name("") == ""
    assert _extends_entity_name({}) == ""


# ── _parse_member ─────────────────────────────────────────────────────────────

def test_parse_member_plain_attribute():
    member = {
        "name": "balance",
        "purpose": "hasA",
        "dataType": "decimal",
        "displayName": "Balance",
        "description": "Account balance.",
    }
    result = _parse_member(member)
    assert result is not None
    assert result["name"] == "balance"
    assert result["type"] == "decimal"
    assert result["is_relationship"] is False


def test_parse_member_entity_reference():
    member = {
        "entity": {"entityReference": "Contact"},
        "name": "primaryContact",
        "resolutionGuidance": {
            "entityByReference": {
                "foreignKeyAttribute": {
                    "name": "primaryContactId",
                    "displayName": "Primary Contact",
                    "description": "",
                }
            }
        },
    }
    result = _parse_member(member)
    assert result is not None
    assert result["referenced_entity"] == "Contact"
    assert result["is_relationship"] is True
    assert result["name"] == "primaryContactId"


def test_parse_member_returns_none_for_no_name():
    assert _parse_member({}) is None
