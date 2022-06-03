"""
GraphNetwork
original: Gabriel Faucher, https://towardsdatascience.com/python-detecting-twitter-bots-with-graphs-and-machine-learning-41269205ab07
modified by: Michael Heichler

Code:
    Base: Python

1. Feed the classifier with a csv
2. Let the classifier search the csv for a Twitter UserID
3. Let the model classify if a specific Twitter UserID is a bot or not
"""

# Import packages
import sys
import json
import csv
import re

import pandas as pd
import numpy as np
from operator import itemgetter

import tweepy
from igraph import *
import networkx as nx
import ast
from karateclub import Graph2Vec
import xgboost as xgb

from helper import TweetGraph, TweetGrabber, RetweetParser


def csvimporter(filename: str, **jsonconstruct):
    """
    Function to clean the csv file from any unnecessary ASCII Chars

    :param jsonconstruct: Awaits a json construct (e.g. from Tweepy)
    :param filename: Is the filename of the csv file if you like to skip the conversion
    :return: a pandas dataframe / saves also a clean CSV file
    """
    if jsonconstruct:
        df = pd.json_normalize(jsonconstruct)
        df.to_csv(f"{filename.replace('#', '_')}.csv")
        # Remove Non-ASCII Chars in hashtags
        df.text.replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)
        # Remove Non-ASCII Chars in hashtags
        df["user.name"].replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)
    else:
        df.read_csv(f"{filename}.csv")
        # Remove Non-ASCII Chars in hashtags
        df.text.replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)
        # Remove Non-ASCII Chars in hashtags
        df["user.name"].replace({r"[^\x00-\x7F]+": ""}, regex=True, inplace=True)

    return df


def igraph_construct(filename: str, username: str):
    """
    This function is a helper function to construct a log graph (undirected, weighted iGraph Object
    :param filename: provided by the graph2vec_construct function
    :param username: provided by the graph2vec construct function
    :return: weighted, undirected iGraph Object (FIXME: return is not required)
    """
    userFrame = pd.read_csv(f"{filename}.csv")
    # The weighted, undirected iGraph object
    log_graph = TweetGraph(edge_list=f"{filename}.csv")

    for key, value in log_graph.e_centrality():
        log_graph.graph.vs.find(name=key)["size"] = value * 20

    log_graph.graph.write_gml(f"{username}.gml")

    return log_graph


def graph2vec_construct(filename: str, username: str):
    """
    First part: Labeling each line in the gml file as a multigraph
    Second part: Reading the gml file with NetworkX to convert each node labeled by name to being labeled by sequential integers (Graph2Vec Requirement)
    Third part: Instantiate a Graph2Vec embedding model, tweaking possible, then fitting the model to the NetworkX Graph + storing the embedding in a Pandas dataframe
    :param filename: Awaits a filename for creating a userFrame pandas dataframe
    :param username: Awaits a username for a better understanding instead of UserID for a clean gml file
    :return: embedded dataframe for prediction
    """
    igraph_construct(filename, username)

    # First part
    igraph_gml = open(f"{username}.gml", "r")
    lof = igraph_gml.readlines()
    igraph_gml.close()
    if lof[4] != "multigraph 1":
        lof.insert(4, "multigraph 1\n")
    igraph_gml = open(f"{username}.gml", "w")
    lof = "".join(lof)
    igraph_gml.write(lof)
    igraph_gml.close()

    # Second part
    H = nx.read_gml(f"{username}.gml", label="name")
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

    return embeddingsframe


def predictment_function(filename: str, username: str):
    embeddingsframe = graph2vec_construct(filename, username)
    classification_model = xgb.XGBClassifier(
        objective="binary:logistic",
        random_state=42,
        learning_rate=0.05,
        n_estimators=5000,
        early_stopping_rounds=10,
    )
    classification_model.load_model("graph_classifier_model.json")

    pred = classification_model.predict(embeddingsframe)
    print(f"{username}:{pred[0]}")

    return pred
