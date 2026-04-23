"""

"""

from __future__ import annotations

from neo4j import GraphDatabase

from app.config import settings

_BASE_TYPES = {"CdsStandard", "CdmEntity", ""}


def _driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def _create_constraints(session) -> None:
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Attribute) REQUIRE (a.name, a.entity_name) IS UNIQUE"
    )


def _load_entities(session, entities: list[dict]) -> None:
    for entity in entities:
        session.run(
            """
            MERGE (e:Entity {name: $name})
            SET e.description   = $description,
                e.extends_entity = $extends_entity
            """,
            name=entity["entity_name"],
            description=entity.get("description", ""),
            extends_entity=entity.get("extends_entity", ""),
        )


def _load_attributes(session, entities: list[dict]) -> None:
    for entity in entities:
        entity_name = entity["entity_name"]
        for attr in entity.get("attributes", []):
            session.run(
                """
                MERGE (e:Entity {name: $entity_name})
                MERGE (a:Attribute {name: $attr_name, entity_name: $entity_name})
                SET a.type         = $type,
                    a.display_name = $display_name,
                    a.description  = $description
                MERGE (e)-[:HAS_ATTRIBUTE]->(a)
                """,
                entity_name=entity_name,
                attr_name=attr["name"],
                type=attr.get("type", ""),
                display_name=attr.get("display_name", ""),
                description=attr.get("description", ""),
            )

        # Relationship attributes become RELATES_TO edges
        for rel in entity.get("relationships", []):
            ref = rel.get("referenced_entity", "")
            if ref:
                session.run(
                    """
                    MERGE (e:Entity {name: $from_entity})
                    MERGE (t:Entity {name: $to_entity})
                    MERGE (e)-[:RELATES_TO {from_attribute: $from_attr}]->(t)
                    """,
                    from_entity=entity_name,
                    to_entity=ref,
                    from_attr=rel.get("name", ""),
                )


def _load_inheritance(session, entities: list[dict]) -> None:
    for entity in entities:
        extends = entity.get("extends_entity", "")
        if extends and extends not in _BASE_TYPES:
            session.run(
                """
                MERGE (e:Entity {name: $name})
                MERGE (p:Entity {name: $parent})
                MERGE (e)-[:INHERITS_FROM]->(p)
                """,
                name=entity["entity_name"],
                parent=extends,
            )


def _load_manifest_relationships(session, relationships: list[dict]) -> None:
    for rel in relationships:
        from_e = rel.get("from_entity", "")
        to_e = rel.get("to_entity", "")
        from_a = rel.get("from_attribute", "")
        to_a = rel.get("to_attribute", "")
        if from_e and to_e and from_a:
            session.run(
                """
                MERGE (f:Entity {name: $from_entity})
                MERGE (t:Entity {name: $to_entity})
                MERGE (f)-[r:RELATES_TO {from_attribute: $from_attr}]->(t)
                SET r.to_attribute = $to_attr
                """,
                from_entity=from_e,
                to_entity=to_e,
                from_attr=from_a,
                to_attr=to_a,
            )


def build_graph(entities: list[dict], manifest_relationships: list[dict]) -> None:
    """Load all entities and relationships into Neo4j."""
    driver = _driver()
    with driver.session() as session:
        _create_constraints(session)
        _load_entities(session, entities)
        _load_attributes(session, entities)
        _load_inheritance(session, entities)
        _load_manifest_relationships(session, manifest_relationships)
    driver.close()
    print(f"Graph loaded: {len(entities)} entities, {len(manifest_relationships)} manifest relationships.")
