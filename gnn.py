import tweepy
import pandas as pd
import os
import numpy as np
import networkx as nx
from karateclub import Graph2Vec
from twitter import api_auth, envHelper, TweetGrabber, RetweetParser, TweetGraph


def tweetInit():
    t = TweetGrabber(
        myApi=os.getenv("api_key"),
        sApi=os.getenv("api_secret"),
        at=os.getenv("access_token"),
        sAt=os.getenv("access_token_secret"),
    )
    return t


def tweetScan(tuser):
    """
    screen_name: Variable to hold whatever Twitter user is being classified
    user_frame: Read the created CSV into a pandas DataFrame for input to RetweetParser class
    r: RetweetParser overwrites the first CSV with a weighted edgelist
    log_graph: The weighted, undirected iGraph object

    NOTE: multiplying the value by some consistent large number creates a more intuitive
          plot, viewing-wise, but doesn't impact classification, since this change is applied
          to all vertices

    :param tuser: Collect the user's mentions into a CSV titled with their username
    :return:
    """
    t = tweetInit()
    screen_name = f"{tuser}"
    print(f"{tuser}")
    t.user_search(user=screen_name, csv_prefix=screen_name)
    userFrame = pd.read_csv(screen_name + ".csv")
    r = RetweetParser(userFrame, screen_name)
    log_graph = TweetGraph(edge_list=screen_name + ".csv")

    for key, value in log_graph.e_centrality():
        log_graph.graph.vs.find(name=key)["size"] = value * 20

    log_graph.graph.write_gml(f=screen_name + ".gml")


def graph2vecinit(tuser):
    """

    :return:
    """
    screen_name = f"{tuser}"
    tweetscan = tweetScan(screen_name)
    igraph_gml = open(screen_name + ".gml", "r")
    lof = igraph_gml.readlines()
    igraph_gml.close()
    if lof[4] != "multigraph 1":
        lof.insert(4, "multigraph 1\n")
    igraph_gml = open(screen_name + ".gml", "w")
    lof = "".join(lof)
    igraph_gml.write(lof)
    igraph_gml.close()

    H = nx.read_gml(screen_name + ".gml", label="name")
    convertedgraph = nx.convert_node_labels_to_integers(H)

    embedding_model = Graph2Vec(dimensions=64)

    embedding_model.fit([convertedgraph])
    embeddingsframe = pd.DataFrame(embedding_model.get_embedding())


if __name__ == "__main__":
    # env = envHelper()
    tweetinit = tweetInit()
    df = pd.DataFrame()
    twitter_screenname = input(f"Enter Twitter User: ")
    tweetscan = tweetScan(twitter_screenname)
    graphvec = graph2vecinit(twitter_screenname)

    # st.title("Twitter GNN Model")
    # choice = st.sidebar.radio("Menu", ["Load Tweets", "Inspect"])
    # if choice == "Load Tweets":
    #    render_main()
    # else:
    #    render_inspect()
