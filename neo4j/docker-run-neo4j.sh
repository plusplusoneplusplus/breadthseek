#!/bin/bash
# Run the latest stable Neo4j with vector support (Enterprise Edition)
# Exposes Bolt (7687) and HTTP (7474) ports, with default password 'neo4j/test'.
# Vector index is enabled by default in recent Neo4j EE (5.15+)

set -e

# Pull the latest stable Neo4j Enterprise image
docker pull neo4j:5.20.0-enterprise

# Run Neo4j with vector index enabled
docker run -d \
  --name neo4j-vector \
  -p7474:7474 -p7687:7687 \
  -e NEO4J_AUTH=neo4j/test \
  -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_server.memory.heap.initial_size=2G \
  -e NEO4J_server.memory.heap.max_size=2G \
  -e NEO4J_dbms.security.procedures.unrestricted=apoc.* \
  -e NEO4J_dbms.security.procedures.allowlist=apoc.* \
  neo4j:5.20.0-enterprise

echo "Neo4j is running at http://localhost:7474 (user: neo4j, pass: test)"
