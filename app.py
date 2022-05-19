from numpy import place
import streamlit as st
import tweepy 
import pandas as pd
from py2neo import Graph, Node, Relationship, NodeMatcher
import os
import json
import re

def send_to_neo(df):
    # get source nodes
    df['source_clean'] = df['source'].apply(lambda x: re.sub('<[^<]+?>', '', x))
    sources = set(df['source_clean'])
    # get hashtag nodes
    hashtags = []
    for i in range(len(df)):
        tmps = json.loads(df['entities.hashtags'][i].replace("'",'"'))
        for c in range(len(tmps)):
            hashtags.append(tmps[c]['text'])
    hashtags = set(hashtags)
    # get user nodes
    # user that sent tweet
    user_col = [col for col in df if col.startswith('user.')]
    user = df[user_col].copy()
    user.drop_duplicates(inplace=True)
    # quoted user
    quoted_user_col = [col for col in df if col.startswith('quoted_status.user.')]
    quoted_user = df[quoted_user_col].copy()
    quoted_user.drop_duplicates(inplace=True)
    quoted_user.columns=quoted_user.columns.str.replace("quoted_status.", "")
    # retweeted user
    retweeted_user_col = [col for col in df if col.startswith('retweeted_status.user.')]
    retweeted_user = df[retweeted_user_col].copy()
    retweeted_user.drop_duplicates(inplace=True)
    retweeted_user.columns=retweeted_user.columns.str.replace("retweeted_status.", "")
    # concat all 
    df_all_user = pd.concat([user, quoted_user, retweeted_user]).drop_duplicates(subset=['user.id'])
    locations = set(df_all_user['user.location'].fillna('na'))
    # initialize neo4j
    graph = Graph("http://localhost:7474", password="1710")
    graph.delete_all()
    # Create all nodes
    for line in sources:
        node = Node("Device", source=line)
        graph.create(node)
    for line in hashtags:
        node = Node("Hashtag", hashtag=line)
        graph.create(node)
    for line in locations:
        node = Node("Location", location=line)
        graph.create(node)
    # Create the Edges
    matcher = NodeMatcher(graph)
    for i in range(len(df_all_user)):
        line = df_all_user.iloc[i].fillna('na')
        id = line['user.id_str']
        name = line['user.screen_name']
        created = line['user.created_at']
        followers = line['user.followers_count']
        node = Node("User", id=id, name=name, created=created, followers=followers)
        node.add_label("User")
        graph.create(node)
        # originates from
        if line['user.location'] != 'na':
            location = matcher.match("Location", location=line['user.location']).first()
            rel = Relationship(node, "originates_from", location)
            graph.create(rel)
    for i in range(len(df)):
        line = df.iloc[i].fillna('na')
        id = line['id_str']
        text = line['text']
        created = line['created_at']
        node = Node("Tweet", id=id, text=text, created=created)
        graph.create(node)
        # tweeted relationship
        user_node = matcher.match("User", id = line['user.id_str']).first()
        rel = Relationship(user_node, "tweeted", node)
        graph.create(rel)
        # uses device
        device = matcher.match("Device", source=line['source_clean']).first()
        rel = Relationship(user_node, "uses", device)
        graph.create(rel)
        # retweeted relationship
        if line['retweeted_status.user.id_str'] != 'na':
            retweeted_user = matcher.match("User", id=line['retweeted_status.user.id_str']).first()
            rel = Relationship(user_node, "retweeted", retweeted_user)
            graph.create(rel)
        # quoted relationship
        if line['quoted_status.user.id_str'] != 'na':
            quoted_user = matcher.match("User", id=line['quoted_status.user.id_str']).first()
            rel = Relationship(user_node, "quoted", quoted_user)
            graph.create(rel)
        # used_hashtag
        tmps = json.loads(line['entities.hashtags'].replace("'",'"'))
        for tmp in tmps:
            hashtag = matcher.match("Hashtag", hashtag=tmp['text']).first()
            rel = Relationship(user_node, "used_hashtag", hashtag)
            graph.create(rel)
        # mentions
        try:
            tmps = json.loads(line['entities.user_mentions'].replace("'",'"'))
            for tmp in tmps:
                user = matcher.match("User", id=tmp['id_str']).first()
                if not user:
                    user = Node("User", id=tmp['id_str'], name=tmp['screen_name'])
                    graph.create(user)
                rel = Relationship(user_node, "mentioned", user)
                graph.create(rel)
        except:
            print(f"Cannot parse {line['entities.user_mentions']}")

def api_auth():
    try:
        api_key= os.getenv("api_key")
        api_secret= os.getenv("api_secret")
        access_token=os.getenv("access_token")
        access_token_secret=os.getenv("access_token_secret")
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth, wait_on_rate_limit=True)
    except:
        print("No API Key provided")
    return api

def load_tweets(search, lang="", n_items=300):
    tweets = tweepy.Cursor(api.search_tweets,
              q=search,
              lang=lang
              ).items(n_items)
    json_data = [r._json for r in tweets]
    df = pd.json_normalize(json_data)
    df.to_csv(f"{search.replace('#', '_')}.csv")

def get_historical():
    files =[file for file in os.listdir("./") if '.csv' in file]
    return files

def load_historical(filename):
    df = pd.read_csv(f"./{filename}", dtype=object)
    return df

def render_main():
    st.header('Collect Tweets from Twitter API to inspect')
    st.write('Due rate-limits only 300 Tweets per 15 Minutes are possible :sunglasses:')
    lang = st.selectbox('Language of Tweets', ("", "de", "en"))
    n_items = st.slider('Number of Tweets', min_value=0, max_value=1200, value=300, step=50)
    search = st.text_input('Search Terms', '#apple')
    new = st.button('Load new Tweets')
    if new:
        load_tweets(search, lang, n_items) 
        st.write("Loaded Data")
        

def render_inspect():
    columns = ["created_at", "id_str", "text", "user.id_str", "user.screen_name"]
    st.subheader("Select a DataFrame")
    historical = st.selectbox('Select a previous run', set(get_historical()))
    hist = st.button('Load Tweets from CSV')
    if hist:
        df = load_historical(historical)
        send_to_neo(df)
        st.write("http://localhost:7474")
        st.dataframe(df[columns])

        

if __name__ == "__main__":
    api = api_auth()
    df = pd.DataFrame()
    st.title('Twitter Network Analysis')
    choice = st.sidebar.radio("Menu", ["Load Tweets", "Inspect"])
    if choice == "Load Tweets":
        render_main()
    else:
        render_inspect()