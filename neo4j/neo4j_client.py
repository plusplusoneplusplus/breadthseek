from neo4j import GraphDatabase

# Update these if you change the docker run config
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "test"

def test_connection():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as session:
        greeting = session.run("RETURN 'Neo4j connection successful!' AS msg").single()["msg"]
        print(greeting)
    driver.close()

if __name__ == "__main__":
    test_connection()
