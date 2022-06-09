from numpy import place
import streamlit as st
import tweepy
import pandas as pd
import py2neo 
import os
import json
import igraph
import re
import xgboost as xgb
from igraph import *
import networkx as nx
from karateclub import Graph2Vec
from helper import TweetGraph, RetweetParser, TweetGrabber

def send_to_neo(df):
    # get source nodes
    #df["source_clean"] = df["source"].apply(lambda x: re.sub("<[^<]+?>", "", x))
    #sources = set(df["source_clean"])
    # get hashtag nodes
    hashtags = []
    for i in range(len(df)):
        try:
            tmps = json.loads(df["entities.hashtags"][i].replace("'", '"'))
            for c in range(len(tmps)):
                hashtags.append(tmps[c]["text"])
        except:
            print(f'Cannot parse hashtag {df["entities.hashtags"][i]}')
    hashtags = set(hashtags)
    # get user nodes
    # user that sent tweet
    user_col = [col for col in df if col.startswith("user.")]
    user = df[user_col].copy()
    user.drop_duplicates(inplace=True)
    # quoted user
    quoted_user_col = [col for col in df if col.startswith("quoted_status.user.")]
    quoted_user = df[quoted_user_col].copy()
    quoted_user.drop_duplicates(inplace=True)
    quoted_user.columns = quoted_user.columns.str.replace("quoted_status.", "")
    # retweeted user
    retweeted_user_col = [col for col in df if col.startswith("retweeted_status.user.")]
    retweeted_user = df[retweeted_user_col].copy()
    retweeted_user.drop_duplicates(inplace=True)
    retweeted_user.columns = retweeted_user.columns.str.replace("retweeted_status.", "")
    # concat all
    df_all_user = pd.concat([user, quoted_user, retweeted_user]).drop_duplicates(
        subset=["user.id"]
    )
    locations = set(df_all_user["user.location"].fillna("na"))
    # initialize neo4j
    graph = py2neo.Graph("http://localhost:7474", password="1710")
    graph.delete_all()
    # Create all nodes
    #for line in sources:
    #    node = py2neo.Node("Device", source=line)
    #    graph.create(node)
    for line in hashtags:
        node = py2neo.Node("Hashtag", hashtag=line)
        graph.create(node)
    for line in locations:
        node = py2neo.Node("Location", location=line)
        graph.create(node)
    # Create the Edges
    matcher = py2neo.NodeMatcher(graph)
    for i in range(len(df_all_user)):
        line = df_all_user.iloc[i].fillna("na")
        id = line["user.id_str"]
        name = line["user.screen_name"]
        created = line["user.created_at"]
        followers = line["user.followers_count"]
        node = py2neo.Node("User", id=id, name=name, created=created, followers=followers)
        node.add_label("User")
        graph.create(node)
        # originates from
        if line["user.location"] != "na":
            location = matcher.match("Location", location=line["user.location"]).first()
            rel = py2neo.Relationship(node, "originates_from", location)
            graph.create(rel)
    for i in range(len(df)):
        line = df.iloc[i].fillna("na")
        id = line["id_str"]
        text = line["text"]
        created = line["created_at"]
        node = py2neo.Node("Tweet", id=id, text=text, created=created)
        graph.create(node)
        # tweeted relationship
        try:
            user_node = matcher.match("User", id=line["user.id_str"]).first()
            rel = py2neo.Relationship(user_node, "tweeted", node)
            graph.create(rel)
        except:
            print(f'Cannot link to user {line["user.id_str"]}')
        # uses device
        #device = matcher.match("Device", source=line["source_clean"]).first()
        #rel = py2neo.Relationship(user_node, "uses", device)
        #graph.create(rel)
        # retweeted relationship
        if line["retweeted_status.user.id_str"] != "na":
            retweeted_user = matcher.match(
                "User", id=line["retweeted_status.user.id_str"]
            ).first()
            rel = py2neo.Relationship(user_node, "retweeted", retweeted_user)
            graph.create(rel)
        # quoted relationship
        if line["quoted_status.user.id_str"] != "na":
            quoted_user = matcher.match(
                "User", id=line["quoted_status.user.id_str"]
            ).first()
            rel = py2neo.Relationship(user_node, "quoted", quoted_user)
            graph.create(rel)
        # used_hashtag
        try:
            tmps = json.loads(line["entities.hashtags"].replace("'", '"'))
            for tmp in tmps:
                hashtag = matcher.match("Hashtag", hashtag=tmp["text"]).first()
                rel = py2neo.Relationship(user_node, "used_hashtag", hashtag)
                graph.create(rel)
        except:
            print(f'cannot parse {line["entities.hashtags"]}')
        # mentions
        try:
            tmps = json.loads(line["entities.user_mentions"].replace("'", '"'))
            for tmp in tmps:
                user = matcher.match("User", id=tmp["id_str"]).first()
                if not user:
                    user = py2neo.Node("User", id=tmp["id_str"], name=tmp["screen_name"])
                    graph.create(user)
                rel = py2neo.Relationship(user_node, "mentioned", user)
                graph.create(rel)
        except:
            print(f"Cannot parse {line['entities.user_mentions']}")


def api_auth():
    try:
        api_key = os.getenv("api_key")
        api_secret = os.getenv("api_secret")
        access_token = os.getenv("access_token")
        access_token_secret = os.getenv("access_token_secret")
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth, wait_on_rate_limit=True)
    except:
        print("No API Key provided")
    return api

def load_tweets(search, lang="", n_items=300):
    tweets = tweepy.Cursor(api.search_tweets, q=search, lang=lang).items(n_items)
    json_data = [r._json for r in tweets]
    df = pd.json_normalize(json_data)
    df.text.replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)
    # Remove Non-ASCII Chars in hashtags
    df["user.name"].replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)
    df.to_csv(f"{search.replace('#', '_')}.csv")


def get_historical():
    files = [file for file in os.listdir("./") if ".csv" in file]
    return files


def load_historical(filename):
    df = pd.read_csv(f"./{filename}", dtype=object)
    return df

def load_model():
    classification_model = xgb.XGBClassifier(
        objective="binary:logistic",
        random_state=42,
        learning_rate=0.05,
        n_estimators=5000,
        early_stopping_rounds=10,
    )
    classification_model.load_model("graph_classifier_model.json")
    return classification_model

def render_main():
    st.header("Collect Tweets from Twitter API to inspect")
    st.write("Due rate-limits only 300 Tweets per 15 Minutes are possible :sunglasses:")
    lang = st.selectbox("Language of Tweets", ("", "de", "en"))
    n_items = st.slider(
        "Number of Tweets", min_value=0, max_value=1200, value=300, step=50
    )
    search = st.text_input("Search Terms", "#apple")
    new = st.button("Load new Tweets")
    if new:
        load_tweets(search, lang, n_items)
        st.write("Loaded Data")


def render_inspect():
    columns = ["created_at", "id_str", "text", "user.id_str", "user.screen_name"]
    st.subheader("Select a DataFrame")
    historical = st.selectbox("Select a previous run", set(get_historical()))
    hist = st.button("Load Tweets from CSV")  
    if hist:
        model = load_model()
        df = load_historical(historical)
        send_to_neo(df)
        st.write("http://localhost:7474")
        st.dataframe(df[columns])

def render_detect():
    # Instantiation
    try:
        consumer_key = os.getenv("api_key")
        consumer_secret = os.getenv("api_secret")
        access_token = os.getenv("access_token")
        access_token_secret = os.getenv("access_token_secret")
    except:
        print("no api key provided")
    
    t = TweetGrabber(myApi = consumer_key, sApi = consumer_secret, at = access_token, sAt = access_token_secret)

    screen_name = st.text_input("User Name")
    detect = st.button("Detect")
    if detect:
        try:
            existing_gml = igraph.read(screen_name + '.gml')
            st.write(screen_name + '.gml already exists.')
        except:
            try:
                print("Scanning activity...")
                # Collect the user's mentions into a CSV titled with their username
                t.user_search(user=screen_name, csv_prefix=screen_name)
                print("Done Scanning")
                # Read the created CSV into a pandas DataFrame for input to RetweetParser class
                userFrame = pd.read_csv(screen_name + ".csv")
                # RetweetParser overwrites the first CSV with a weighted edgelist
                r = RetweetParser(userFrame, screen_name)
                print("Parsed Retweets")
                # The weighted, undirected iGraph object
                log_graph = TweetGraph(edge_list= screen_name + ".csv")

                # Add 'size' attribute to each vertex based on its Eigencentrality
                # NOTE: multiplying the value by some consistent large number creates a more intuitive
                # plot, viewing-wise, but doesn't impact classification, since this change is applied
                # to all vertices
                for key, value in log_graph.e_centrality():
                    log_graph.tuple_graph.vs.find(name=key)['size'] = value*20

                # Save the graph in GML format
                print("Building gml...")
                log_graph.tuple_graph.write_gml(f=screen_name+".gml")

                # Plot the graph for viewing
                # style = {}
                # style["edge_curved"] = False
                # style["vertex_label"] = m_graph.tuple_graph.vs['name']
                # style["vertex_label_size"] = 5
                # plot(m_graph.tuple_graph, **style)
            except:
                print(screen_name + ' graphing failed.')


        # 2. GML conversion to Graph2Vec vector

        # Believe it or not, the easiest way I found of doing this was to
        # now open the GML files in NetworkX instead of iGraph. 

        # In order to do so, I first had to insert a line manually labeling 
        # each as a multigraph with this very messy chunk of code.
        igraph_gml = open(screen_name+".gml", 'r')
        lof = igraph_gml.readlines()
        igraph_gml.close()
        if lof[4]!="multigraph 1":
            lof.insert(4, "multigraph 1\n")
        igraph_gml = open(screen_name + '.gml', 'w')
        lof = "".join(lof)
        igraph_gml.write(lof)
        igraph_gml.close()

        # Next, read the GML with NetworkX, then convert each
        # node from being labeled by name to being labeled by sequential
        # integers, since Graph2Vec requires nodes to be labeled this way
        st.write("Creating vector embedding...")
        H = nx.read_gml(screen_name + '.gml', label='name')
        convertedgraph = nx.convert_node_labels_to_integers(H)

        # Instantiate a Graph2Vec embedding model. There are
        # a variety of parameters that can be changed when 
        # instantiating the model (see the above link to the Karate Club library),
        # but I found 64 feature columns and otherwise default parameters
        # to provide the best results
        embedding_model = Graph2Vec(dimensions=64)
        # Now, fit the model to the NetworkX graph, and store the embedding
        # in a pandas DataFrame
        embedding_model.fit([convertedgraph])
        embeddingsframe = pd.DataFrame(embedding_model.get_embedding())

        # 3. Use XGBoost classification model to predict user type based on vector,
        # and output prediction and plot of user's GML representation

        #Load classification model and make a prediction
        classification_model = xgb.XGBClassifier(objective="binary:logistic", random_state=42, learning_rate = 0.05, n_estimators = 5000, early_stopping_rounds = 10)
        classification_model.load_model('graph_classifier_3.json')
        st.write("Predicting...")
        pred = classification_model.predict(embeddingsframe)

        st.write(screen_name + ': ' + pred[0])




if __name__ == "__main__":
    cache = './cache/'
    api = api_auth()
    df = pd.DataFrame()
    st.title("Twitter Network Analysis")
    choice = st.sidebar.radio("Menu", ["Load Tweets", "Inspect", "Detect"])
    if choice == "Load Tweets":
        render_main()
    elif choice == "Inspect":
        render_inspect()
    elif choice == "Detect":
        render_detect()
