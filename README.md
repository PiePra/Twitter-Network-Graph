# Twitter-Network-Graph

Start Neo4j

```bash
podman run --publish=7474:7474 --publish=7687:7687 \
    --volume=$HOME/neo4j/data:/data docker.io/neo4j
```

Run Streamlit App

```bash
streamlit run app.py
```