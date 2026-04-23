# Benchmark Queries — Vector vs Hybrid KG

These queries demonstrate where each retrieval path wins.
Run them against `/query/compare` to see the difference live.

---

## 1. Simple attribute lookup — Vector wins (or ties)

**Query:** `"What fields does Bank have?"`

**Why vector is sufficient:**  
The Bank entity chunk contains all its own attributes in one document.
Cosine similarity lands the right entity immediately; graph traversal adds
no new information for a single-entity, flat question.

**Expected behaviour:** both paths return the same answer; hybrid takes slightly
longer because it still traverses the graph unnecessarily.

---

## 2. Multi-hop relationship — KG wins clearly

**Query:** `"Which branch is responsible for a customer's loan?"`

**Why vector falls short:**  
No single entity chunk contains the full path
`Contact → CommercialLoan → Branch`.
The vector path retrieves one or two loosely related chunks and the LLM
cannot connect the entities without the explicit edge data.

**Why KG wins:**  
The graph traversal walks `CommercialLoan -[:RELATES_TO]-> Branch` and
`Contact -[:RELATES_TO]-> CommercialLoan` in 1-2 hops, returning a
structured subgraph the LLM can reason over precisely.

---

## 3. Inheritance / all-fields question — KG wins

**Query:** `"What are ALL the fields on Contact, including inherited ones?"`

**Why vector falls short:**  
The Contact chunk only contains attributes added at the banking-schema scope.
Inherited fields from the CRM base Contact are not in that chunk, so the
vector answer is incomplete.

**Why KG wins:**  
The `INHERITS_FROM` edge lets the graph traversal walk up to the parent entity
and collect its `HAS_ATTRIBUTE` nodes, giving the LLM the full resolved
attribute set.

---

## 4. Cross-entity semantic search — Vector wins

**Query:** `"What entities deal with financial products?"`

**Why vector wins:**  
This is a broad semantic question with no specific relationship to traverse.
Cosine similarity naturally surfaces `FinancialProduct`, `CommercialLoan`,
`CertificateOfDeposit` etc. from their descriptions.
Graph traversal from any one entry node adds noise rather than signal.

---

## Running the benchmarks

```bash
curl -s -X POST http://localhost:8000/query/compare \
  -H "Content-Type: application/json" \
  -d '{"question": "Which branch is responsible for a customer loan?"}' \
  | python3 -m json.tool
```
