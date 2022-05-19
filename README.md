# Twitter-Network-Graph

Start Neo4j

```bash
podman run --publish=7474:7474 --publish=7687:7687 \
    --volume=$HOME/neo4j/data:/data docker.io/neo4j
```
Create .env File like
```
api_key="..."
api_secret="..."
access_token="..."
access_token_secret="..."
```
Source API Env Vars
```bash
source .env
```

Source API Env Vars
```bash
source .env
```

Run Streamlit App

```bash
streamlit run app.py
```
