# Vector DB & ChromaDB — Concepts and Working


![VectorDB](/vectordb-lab/vector_db_explained.png)

---

## 1. The Core Problem — Why Vector DBs Exist

A traditional database stores and searches by **exact values**:

```sql
SELECT * FROM filings WHERE section = 'Risk Factors'
```

But meaning doesn't work that way. These three sentences mean roughly the same thing:

```
"Apple disclosed AI governance risks"
"Apple warned about machine learning regulation"
"AAPL faces liability from automated decision systems"
```

A SQL query for "AI governance risks" returns **zero results** for the 2nd and 3rd sentences even though they're semantically identical. Vector databases solve this by searching by **meaning**, not exact words.

---

## 2. What is an Embedding?

An embedding is a **list of numbers that represents the meaning of text**. An embedding model (like OpenAI's `text-embedding-3-small`) reads your text and outputs a vector — a fixed-length array of floating point numbers.

```python
"Apple disclosed AI risks" → [0.21, -0.45, 0.87, 0.03, ..., 0.61]  # 1536 numbers
"AAPL faces AI liability"  → [0.19, -0.41, 0.85, 0.07, ..., 0.58]  # 1536 numbers
"The weather is sunny"     → [-0.72, 0.33, -0.12, 0.91, ..., -0.44] # 1536 numbers
```

The first two are **semantically similar** so their numbers are close. The third is unrelated so its numbers are far away. The model has learned during training that AI-related concepts cluster together in this 1536-dimensional space.

---

## 3. What is Vector Space?

Think of it as a coordinate system — but instead of 2D (x, y) or 3D (x, y, z), it's **1536-dimensional**. Every document you index gets plotted as a point in this space based on its embedding.

**2D simplified analogy:**

```
         AI/Technology Axis
              ↑
    AAPL risk |  • "Apple AI governance risks"
    disclosure|  • "AAPL machine learning liability"  
              |
              |                    • "Meta AI capex"
              |
──────────────────────────────────→  Investment Axis
              |
              |      • "Remote work HR policy"
              |
              ↓
```

Documents about similar topics cluster together. When you search, your query gets embedded into the same space, and ChromaDB finds the **nearest neighboring points**.

---

## 4. How Similarity is Measured

ChromaDB supports three distance metrics. For text, **cosine similarity** is the right choice.

**Cosine Similarity** measures the **angle** between two vectors, not the distance between points. This means two documents can be long or short — what matters is the direction they point.

```
Cosine Similarity = 1.0  → identical meaning (angle = 0°)
Cosine Similarity = 0.5  → somewhat related  (angle = 60°)
Cosine Similarity = 0.0  → completely unrelated (angle = 90°)
```

| Metric | Measures | Best For |
|---|---|---|
| `cosine` | Angle between vectors | Text (direction matters, not magnitude) |
| `l2` | Euclidean distance | Image embeddings |
| `ip` | Dot product | Pre-normalized vectors |

> **Critical:** ChromaDB returns **cosine distance** (not similarity). That's why your notebook does:

```python
similarity = 1.0 - distance  # Convert distance → similarity
```

---

## 5. How ChromaDB Works Internally — HNSW

Naively, comparing your query vector against every stored vector would be too slow at scale. ChromaDB uses **HNSW (Hierarchical Navigable Small World)** — a graph-based index structure that makes search fast without comparing everything.

Think of it like a highway system:

```
Layer 2 (Highway):     A ──────────────── E
                       |                  |
Layer 1 (Main roads):  A ── B ── C ── D ── E
                       |    |         |    |
Layer 0 (All docs):    A─a1─B─b1─b2─C─c1─D─d1─E
```

When you search:
1. Start at the top layer — take big jumps to get close to your query
2. Drop down to finer layers — take smaller steps to find exact neighbors
3. Return top-k results

This makes search `O(log n)` instead of `O(n)` — orders of magnitude faster at scale.

---

## 6. End-to-End Flow in ChromaDB

Here's exactly what happens when you run your lab code:

```
┌──────────────────────────────────────────────────────────────────┐
│                        INDEXING TIME                             │
│                                                                  │
│  "Apple AI governance risks"                                     │
│           │                                                      │
│           ▼                                                      │
│  OpenAI text-embedding-3-small                                   │
│           │                                                      │
│           ▼                                                      │
│  [0.21, -0.45, 0.87, ..., 0.61]  ← 1536-dim vector               │
│           │                                                      │
│           ▼                                                      │
│  HNSW Graph Index  +  Metadata Store  +  Document Store          │
│  (the vector)         (ticker, year)    (original text)          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        QUERY TIME                                │
│                                                                  │
│  "What AI risks has Apple disclosed?"                            │
│           │                                                      │
│           ▼                                                      │
│  OpenAI text-embedding-3-small                                   │
│           │                                                      │
│           ▼                                                      │
│  [0.19, -0.41, 0.85, ..., 0.58]  ← query vector                  │
│           │                                                      │
│           ▼                                                      │
│  HNSW Graph Search → finds nearest neighbors                     │
│           │                                                      │
│           ▼                                                      │
│  Returns: doc_ids + distances + documents + metadatas            │
│           │                                                      │
│           ▼                                                      │
│  similarity = 1.0 - distance                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. What the Metadata Store Does

ChromaDB stores three things per document:

```
┌──────────────────────────────────────────────────────┐
│  Document ID:  "aapl-risk-2024"                      │
│                                                      │
│  Vector:       [0.21, -0.45, 0.87, ..., 0.61]        │
│                ← used for similarity search          │
│                                                      │
│  Document:     "Apple disclosed AI governance..."    │
│                ← returned to user                    │
│                                                      │
│  Metadata:     {"ticker": "AAPL",                    │
│                 "section": "Risk Factors",           │
│                 "year": 2024}                        │
│                ← used for filtering                  │
└──────────────────────────────────────────────────────┘
```

The metadata filter runs **before** the vector search, narrowing the search space. So `where={"ticker": "AAPL"}` first isolates Apple documents, then runs HNSW only within that subset.

---

## 8. Where Dense Retrieval Breaks — The Vocabulary Gap

Dense retrieval is powerful but has two known failure modes:

**Failure 1 — Rare Jargon:**

```
Query:    "BM25 score"
ChromaDB: Might return generic "search algorithm" docs
          because "BM25" is rare in training data → poor embedding
BM25:     Nails it with exact keyword match
```

**Failure 2 — Very Short Queries:**

```
Query:    "10-K AI"
ChromaDB: Only 2 tokens → very little semantic signal to embed
HyDE fix: Generate a hypothetical answer first, embed that instead
```

> This is precisely why your notebook combines BM25 + ChromaDB + RRF + HyDE — each technique patches the weaknesses of the others.

---

## 9. The Complete Mental Model

```
Text Meaning
     │
     ▼
Embedding Model → converts meaning to numbers (vector)
     │
     ▼
Vector Space → plots all documents as points
     │
     ▼
HNSW Index → fast graph-based nearest neighbor search
     │
     ▼
Cosine Distance → measures angle between query and documents
     │
     ▼
Top-K Results → most semantically similar documents returned
     │
     ▼
Metadata Filter → structured narrowing on top of semantic search
```

---

# Reference Links

Visual Example: [Embedding projector - visualization of high-dimensional data](https://projector.tensorflow.org/)

Chroma DB - [Introduction - Chroma Docs](https://docs.trychroma.com/docs/overview/introduction)