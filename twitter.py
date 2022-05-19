import os
import tweepy
import numpy as np


def envHelper():
    apikey = input(f"Enter API Key: ")
    apisecret = input(f"Enter API Secret: ")
    accesstoken = input(f"Enter Access Token: ")
    accesstokensecret = input(f"Enter Access Token Secret: ")
    os.environ["api_key"] = apikey
    os.environ["api_secret"] = apisecret
    os.environ["access_token"] = accesstoken
    os.environ["access_token_secret"] = accesstokensecret


def api_auth():
    try:
        api_key = os.getenv("api_key")
        api_secret = os.getenv("api_secret")
        access_token = os.getenv("access_token")
        access_token_secret = os.getenv("access_token_secret")
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(
            auth,
            wait_on_rate_limit=True,
            wait_on_rate_limit_notify=True,
            tweet_mode="extended",
        )
    except:
        print("No API Key provided")
    return api


class TweetGrabber:
    def __init__(self, myApi, sApi, at, sAt):
        import tweepy

        print(myApi)
        self.tweepy = tweepy
        auth = tweepy.OAuthHandler(myApi, sApi)
        auth.set_access_token(at, sAt)
        self.api = tweepy.API(auth)

    def strip_non_ascii(self, string):
        """Returns the string without non ASCII characters"""
        stripped = (c for c in string if 0 < ord(c) < 127)
        return "".join(stripped)

    def keyword_search(self, keyword, csv_prefix):
        import csv

        API_results = self.api.search(
            q=keyword, rpp=1000, show_user=True, tweet_mode="extended"
        )

        with open(f"{csv_prefix}.csv", "w", newline="") as csvfile:
            fieldnames = [
                "tweet_id",
                "tweet_text",
                "date",
                "user_id",
                "follower_count",
                "retweet_count",
                "user_mentions",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for tweet in API_results:
                text = self.strip_non_ascii(tweet.full_text)
                date = tweet.created_at.strftime("%m/%d/%Y")
                writer.writerow(
                    {
                        "tweet_id": tweet.id_str,
                        "tweet_text": text,
                        "date": date,
                        "user_id": tweet.user.id_str,
                        "follower_count": tweet.user.followers_count,
                        "retweet_count": tweet.retweet_count,
                        "user_mentions": tweet.entities["user_mentions"],
                    }
                )

    def user_search(self, user, csv_prefix):
        import csv

        API_results = self.tweepy.Cursor(
            self.api.user_timeline, user_id="user_name", tweet_mode="extended", count=50
        ).items()

        with open(f"{csv_prefix}.csv", "w", newline="") as csvfile:
            fieldnames = [
                "tweet_id",
                "tweet_text",
                "date",
                "user_id",
                "user_mentions",
                "retweet_count",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for tweet in API_results:
                text = self.strip_non_ascii(tweet.full_text)
                date = tweet.created_at.strftime("%m/%d/%Y")
                writer.writerow(
                    {
                        "tweet_id": tweet.id_str,
                        "tweet_text": text,
                        "date": date,
                        "user_id": tweet.user.id_str,
                        "user_mentions": tweet.entities["user_mentions"],
                        "retweet_count": tweet.retweet_count,
                    }
                )


class RetweetParser:
    def __init__(self, data, user):
        import ast

        self.user = user

        edge_list = []

        for idx, row in data.iterrows():
            if len(row[4]) > 5:
                user_account = user
                weight = np.log(row[5] + 1)
                for idx_1, item in enumerate(ast.literal_eval(row[4])):
                    edge_list.append((user_account, item["screen_name"], weight))

                    for idx_2 in range(idx_1 + 1, len(ast.literal_eval(row[4]))):
                        name_a = ast.literal_eval(row[4])[idx_1]["screen_name"]
                        name_b = ast.literal_eval(row[4])[idx_2]["screen_name"]

                        edge_list.append((name_a, name_b, weight))

        import csv

        with open(f"{self.user}.csv", "w", newline="") as csvfile:
            fieldnames = ["user_a", "user_b", "log_retweet"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in edge_list:
                writer.writerow(
                    {"user_a": row[0], "user_b": row[1], "log_retweet": row[2]}
                )


class TweetGraph:
    def __init__(self, edge_list):
        import igraph
        import pandas as pd

        data = pd.read_csv(edge_list).to_records(index=False)
        self.graph = igraph.Graph.TupleList(data, weights=True, directed=False)

    def e_centrality(self):
        import operator

        vectors = self.graph.eigenvector_centrality()
        e = {
            name: cen for cen, name in zip([v for v in vectors], self.graph.vs["name"])
        }
        return sorted(e.items(), key=operator.itemgetter(1), reverse=True)
