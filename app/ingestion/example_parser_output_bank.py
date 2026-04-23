{
  "entity_name": "Bank",
  "description": "The physical bank location which contains information such as the name and location of the bank.",
  "extends_entity": "CdsStandard",
  "attributes": [
    {
      "name": "addressLine1",
      "type": "string",
      "display_name": "Address Line 1",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "addressLine2",
      "type": "string",
      "display_name": "Address Line 2",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "addressLine3",
      "type": "string",
      "display_name": "Address Line 3",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "bankCode",
      "type": "string",
      "display_name": "Bank Code",
      "description": "Bank Code",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "bankId",
      "type": "entityId",
      "display_name": "Bank",
      "description": "Unique identifier for entity instances",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "bankName",
      "type": "name",
      "display_name": "Bank Name",
      "description": "The name of the custom entity",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "country",
      "type": "country",
      "display_name": "Country",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "state",
      "type": "string",
      "display_name": "State",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "telelphoneNo",
      "type": "phone",
      "display_name": "Telelphone No.",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "zipCodes",
      "type": "string",
      "display_name": "Zip Codes",
      "description": "",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "stateCode",
      "type": "listLookup",
      "display_name": "Status",
      "description": "Status of the Bank",
      "enum_values": [
        "Active",
        "Inactive"
      ],
      "referenced_entity": "",
      "is_relationship": false
    },
    {
      "name": "statusCode",
      "type": "listLookupCorrelated",
      "display_name": "Status Reason",
      "description": "Reason for the status of the Bank",
      "enum_values": [],
      "referenced_entity": "",
      "is_relationship": false
    }
  ],
  "relationships": [],
  "source_path": "cdm-data/schemaDocuments/core/applicationCommon/foundationCommon/crmCommon/accelerators/financialServices/banking/Bank.cdm.json"
}