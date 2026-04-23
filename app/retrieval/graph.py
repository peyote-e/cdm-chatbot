"""Neo4j graph queries for CDM entity traversal."""

from __future__ import annotations

from neo4j import GraphDatabase

from app.config import settings


def _driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def get_entity_subgraph(entity_names: list[str], hop_depth: int = 1) -> dict:
    """
    Return a structured subgraph rooted at entity_names.

    hop_depth=1  direct attributes + immediate neighbours
    hop_depth=2  also pulls neighbours-of-neighbours (for multi-hop questions)
    """
    driver = _driver()
    with driver.session() as session:
        # Core entities with their own attributes and parents
        entity_rows = session.run(
            """
            MATCH (e:Entity)
            WHERE e.name IN $names
            OPTIONAL MATCH (e)-[:HAS_ATTRIBUTE]->(a:Attribute)
            OPTIONAL MATCH (e)-[:INHERITS_FROM]->(parent:Entity)
            RETURN e.name        AS name,
                   e.description AS description,
                   e.extends_entity AS extends_entity,
                   collect(DISTINCT {
                       name:         a.name,
                       type:         a.type,
                       display_name: a.display_name,
                       description:  a.description
                   }) AS attributes,
                   collect(DISTINCT parent.name) AS parents
            """,
            names=entity_names,
        ).data()

        # Relationships from entry nodes (and their 2-hop neighbours if requested)
        depth_clause = (
            "(e)-[:RELATES_TO*1..2]->(neighbour:Entity)"
            if hop_depth >= 2
            else "(e)-[:RELATES_TO]->(neighbour:Entity)"
        )
        rel_rows = session.run(
            f"""
            MATCH (e:Entity)
            WHERE e.name IN $names
            MATCH {depth_clause}
            RETURN e.name          AS from_entity,
                   neighbour.name  AS to_entity
            """,
            names=entity_names,
        ).data()

    driver.close()

    # Clean up empty attribute stubs (OPTIONAL MATCH can yield {{name: null, ...}})
    for row in entity_rows:
        row["attributes"] = [
            a for a in row.get("attributes", []) if a.get("name")
        ]
        row["parents"] = [p for p in row.get("parents", []) if p]

    return {
        "entities":      entity_rows,
        "relations":     rel_rows,
        "entry_names":   entity_names,
        "hop_depth":     hop_depth,
    }


def list_all_entities() -> list[dict]:
    driver = _driver()
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (e:Entity)
            OPTIONAL MATCH (e)-[:HAS_ATTRIBUTE]->(a:Attribute)
            RETURN e.name        AS name,
                   e.description AS description,
                   count(a)      AS attribute_count
            ORDER BY e.name
            """
        ).data()
    driver.close()
    return rows


def get_entity_detail(name: str) -> dict | None:
    driver = _driver()
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (e:Entity {name: $name})
            OPTIONAL MATCH (e)-[:HAS_ATTRIBUTE]->(a:Attribute)
            OPTIONAL MATCH (e)-[:INHERITS_FROM]->(parent:Entity)
            OPTIONAL MATCH (e)-[r:RELATES_TO]->(neighbour:Entity)
            RETURN e.name            AS name,
                   e.description     AS description,
                   e.extends_entity  AS extends_entity,
                   collect(DISTINCT {
                       name:         a.name,
                       type:         a.type,
                       display_name: a.display_name,
                       description:  a.description
                   }) AS attributes,
                   collect(DISTINCT parent.name)    AS parents,
                   collect(DISTINCT {
                       to_entity:      neighbour.name,
                       from_attribute: r.from_attribute
                   }) AS relations
            """,
            name=name,
        ).data()
    driver.close()

    if not rows:
        return None

    row = rows[0]
    row["attributes"] = [a for a in row.get("attributes", []) if a.get("name")]
    row["relations"]  = [r for r in row.get("relations", [])  if r.get("to_entity")]
    row["neighbors"]  = list({r["to_entity"] for r in row["relations"]})
    return row
