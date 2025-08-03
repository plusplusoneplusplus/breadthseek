from neo4j import GraphDatabase

# Update these if you change the docker run config
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "testtest"

def test_connection():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        greeting = session.run("RETURN 'Neo4j connection successful!' AS msg").single()["msg"]
        print(greeting)
    driver.close()


import time
import random

import numpy as np

def benchmark_neo4j(num_persons=100, num_knows=300, num_queries=50):
    """
    LDBC SNB-inspired benchmark: create Person nodes, KNOWS relationships, and run standard queries.
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        # Clean up any previous test data
        session.run("MATCH (n:Person) DETACH DELETE n")

        # Create Person nodes
        persons = []
        start_write = time.time()
        for i in range(num_persons):
            props = {
                "id": i,
                "firstName": f"First{i}",
                "lastName": f"Last{i}",
                "birthday": f"19{random.randint(60, 99)}-01-01"
            }
            session.run("CREATE (p:Person {id: $id, firstName: $firstName, lastName: $lastName, birthday: $birthday})", props)
            persons.append(i)
        end_write = time.time()
        write_time = end_write - start_write

        # Create KNOWS relationships (random pairs)
        start_rel = time.time()
        for _ in range(num_knows):
            a, b = random.sample(persons, 2)
            session.run("MATCH (a:Person {id: $a}), (b:Person {id: $b}) CREATE (a)-[:KNOWS]->(b)", {"a": a, "b": b})
        end_rel = time.time()
        rel_time = end_rel - start_rel

        # Friends-of-friends (2-hop) query benchmark
        start_fof = time.time()
        for _ in range(num_queries):
            pid = random.choice(persons)
            session.run("MATCH (p:Person {id: $id})-[:KNOWS]->()-[:KNOWS]->(fof) RETURN count(DISTINCT fof) as fof_count", {"id": pid})
        end_fof = time.time()
        fof_time = end_fof - start_fof

        # Shortest path query benchmark
        start_path = time.time()
        for _ in range(num_queries):
            a, b = random.sample(persons, 2)
            session.run("MATCH (a:Person {id: $a}), (b:Person {id: $b}) CALL apoc.algo.dijkstra(a, b, 'KNOWS', 'weight') YIELD path RETURN length(path) as len", {"a": a, "b": b})
        end_path = time.time()
        path_time = end_path - start_path

        # Aggregation: count direct friends
        start_agg = time.time()
        for _ in range(num_queries):
            pid = random.choice(persons)
            session.run("MATCH (p:Person {id: $id})-[:KNOWS]->(f) RETURN count(f) as friend_count", {"id": pid})
        end_agg = time.time()
        agg_time = end_agg - start_agg

        print(f"Neo4j LDBC SNB-inspired Benchmark Results:")
        print(f"  Write: {num_persons} Person nodes in {write_time:.4f} seconds ({num_persons/write_time:.2f} nodes/sec)")
        print(f"  Write: {num_knows} KNOWS relationships in {rel_time:.4f} seconds ({num_knows/rel_time:.2f} rels/sec)")
        print(f"  Friends-of-friends queries: {num_queries} in {fof_time:.4f} seconds ({num_queries/fof_time:.2f} qps)")
        print(f"  Shortest path queries: {num_queries} in {path_time:.4f} seconds ({num_queries/path_time:.2f} qps)")
        print(f"  Aggregation queries: {num_queries} in {agg_time:.4f} seconds ({num_queries/agg_time:.2f} qps)")

    driver.close()


# --- VectorDB Benchmark for Neo4j ---
def benchmark_neo4j_vectordb(num_nodes=1000, dim=1536, num_queries=20, k=5):
    """
    Benchmark Neo4j vector index: insert nodes with random embeddings, create index, run ANN queries.
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        # Clean up previous test data
        session.run("MATCH (n:VecTest) DETACH DELETE n")

        # Generate and insert nodes with random embeddings
        start_insert = time.time()
        for i in range(num_nodes):
            embedding = np.random.normal(size=dim).astype(float).tolist()
            session.run(
                "CREATE (n:VecTest {id: $id, embedding: $embedding})",
                {"id": i, "embedding": embedding}
            )
        end_insert = time.time()
        insert_time = end_insert - start_insert

        # Create vector index (if not exists)
        index_name = "vecTestEmbedding"
        start_index = time.time()
        session.run(f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (n:VecTest) ON (n.embedding)
            OPTIONS {{ indexConfig: {{
                `vector.dimensions`: {dim},
                `vector.similarity_function`: 'cosine'
            }} }}
        """)
        # Wait for index to be online
        while True:
            result = session.run(f"SHOW VECTOR INDEXES YIELD name, state WHERE name = '{index_name}' RETURN state").single()
            if result and result["state"] == "ONLINE":
                break
            time.sleep(0.2)
        end_index = time.time()
        index_time = end_index - start_index

        # Run ANN queries
        start_query = time.time()
        for _ in range(num_queries):
            query_vec = np.random.normal(size=dim).astype(float).tolist()
            session.run(
                f"CALL db.index.vector.queryNodes('{index_name}', $k, $query) YIELD node, score RETURN node.id, score",
                {"k": k, "query": query_vec}
            )
        end_query = time.time()
        query_time = end_query - start_query

        print(f"Neo4j VectorDB Benchmark Results:")
        print(f"  Insert: {num_nodes} nodes with {dim}-dim embeddings in {insert_time:.4f} seconds ({num_nodes/insert_time:.2f} nodes/sec)")
        print(f"  Index: vector index creation in {index_time:.4f} seconds")
        print(f"  ANN queries: {num_queries} queries (top {k}) in {query_time:.4f} seconds ({num_queries/query_time:.2f} qps)")

    driver.close()


# --- Graph RAG-like Benchmark for Neo4j ---
def benchmark_neo4j_graphrag(num_files=50, classes_per_file=5, funcs_per_class=5, dim=384, num_queries=10, k=5, expand_hops=1):
    """
    Benchmark: Graph RAG hybrid retrieval (vector + graph) on a synthetic codebase graph.
    - Nodes: File, Class, Function (each with embedding)
    - Relationships: FILE-CONTAINS->CLASS, CLASS-CONTAINS->FUNCTION, CLASS-CALLS->FUNCTION
    - For each query: vector search + graph expansion
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        # Clean up previous test data
        session.run("MATCH (n:File) DETACH DELETE n")
        session.run("MATCH (n:Class) DETACH DELETE n")
        session.run("MATCH (n:Function) DETACH DELETE n")

        # Insert files, classes, functions with embeddings
        start_insert = time.time()
        file_ids = []
        class_ids = []
        func_ids = []
        for f in range(num_files):
            file_id = f"file_{f}"
            file_emb = np.random.normal(size=dim).astype(float).tolist()
            session.run("CREATE (f:File {id: $id, embedding: $embedding})", {"id": file_id, "embedding": file_emb})
            file_ids.append(file_id)
            for c in range(classes_per_file):
                class_id = f"class_{f}_{c}"
                class_emb = np.random.normal(size=dim).astype(float).tolist()
                session.run("CREATE (c:Class {id: $id, embedding: $embedding})", {"id": class_id, "embedding": class_emb})
                class_ids.append(class_id)
                # FILE-CONTAINS->CLASS
                session.run("MATCH (f:File {id: $fid}), (c:Class {id: $cid}) CREATE (f)-[:CONTAINS]->(c)", {"fid": file_id, "cid": class_id})
                for fn in range(funcs_per_class):
                    func_id = f"func_{f}_{c}_{fn}"
                    func_emb = np.random.normal(size=dim).astype(float).tolist()
                    session.run("CREATE (fn:Function {id: $id, embedding: $embedding})", {"id": func_id, "embedding": func_emb})
                    func_ids.append(func_id)
                    # CLASS-CONTAINS->FUNCTION
                    session.run("MATCH (c:Class {id: $cid}), (fn:Function {id: $fid}) CREATE (c)-[:CONTAINS]->(fn)", {"cid": class_id, "fid": func_id})
        # Add some random CALLS relationships between classes and functions
        for _ in range(num_files * classes_per_file):
            c = random.choice(class_ids)
            f = random.choice(func_ids)
            session.run("MATCH (c:Class {id: $cid}), (fn:Function {id: $fid}) CREATE (c)-[:CALLS]->(fn)", {"cid": c, "fid": f})
        end_insert = time.time()
        insert_time = end_insert - start_insert

        # Create vector index on all entity types
        start_index = time.time()
        session.run(f"""
            CREATE VECTOR INDEX fileEmb IF NOT EXISTS FOR (n:File) ON (n.embedding) OPTIONS {{ indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}} }}
        """)
        session.run(f"""
            CREATE VECTOR INDEX classEmb IF NOT EXISTS FOR (n:Class) ON (n.embedding) OPTIONS {{ indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}} }}
        """)
        session.run(f"""
            CREATE VECTOR INDEX funcEmb IF NOT EXISTS FOR (n:Function) ON (n.embedding) OPTIONS {{ indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}} }}
        """)
        # Wait for all indexes to be online
        for idx in ["fileEmb", "classEmb", "funcEmb"]:
            while True:
                result = session.run(f"SHOW VECTOR INDEXES YIELD name, state WHERE name = '{idx}' RETURN state").single()
                if result and result["state"] == "ONLINE":
                    break
                time.sleep(0.2)
        end_index = time.time()
        index_time = end_index - start_index

        # Hybrid retrieval benchmark
        start_query = time.time()
        for _ in range(num_queries):
            # Simulate a user query as a random vector
            query_vec = np.random.normal(size=dim).astype(float).tolist()
            # 1. Vector search: top-k from all entity types
            file_hits = session.run(f"CALL db.index.vector.queryNodes('fileEmb', $k, $query) YIELD node, score RETURN node.id, score", {"k": k, "query": query_vec}).data()
            class_hits = session.run(f"CALL db.index.vector.queryNodes('classEmb', $k, $query) YIELD node, score RETURN node.id, score", {"k": k, "query": query_vec}).data()
            func_hits = session.run(f"CALL db.index.vector.queryNodes('funcEmb', $k, $query) YIELD node, score RETURN node.id, score", {"k": k, "query": query_vec}).data()
            # 2. Graph expansion: for each hit, expand neighbors (1 hop)
            all_ids = [h['node.id'] for h in file_hits + class_hits + func_hits]
            for nid in all_ids:
                session.run("MATCH (n {id: $id})--(nbr) RETURN nbr.id LIMIT 10", {"id": nid})
        end_query = time.time()
        query_time = end_query - start_query

        print(f"Neo4j GraphRAG Benchmark Results:")
        print(f"  Insert: {num_files} files, {len(class_ids)} classes, {len(func_ids)} functions in {insert_time:.4f} seconds")
        print(f"  Index: vector index creation in {index_time:.4f} seconds")
        print(f"  Hybrid queries: {num_queries} queries (top {k} per type, {expand_hops} hop) in {query_time:.4f} seconds ({num_queries/query_time:.2f} qps)")

    driver.close()

if __name__ == "__main__":
    test_connection()

    print("\nRunning Neo4j LDBC SNB-inspired benchmark...")
    benchmark_neo4j(num_persons=100, num_knows=300, num_queries=50)

    print("\nRunning Neo4j VectorDB benchmark...")
    benchmark_neo4j_vectordb(num_nodes=1000, dim=1536, num_queries=20, k=5)

    print("\nRunning Neo4j GraphRAG benchmark...")
    benchmark_neo4j_graphrag(num_files=30, classes_per_file=4, funcs_per_class=4, dim=384, num_queries=10, k=5, expand_hops=1)
