import tweepy
import igraph
import pandas as pd
import numpy as np
import csv
import ast
from igraph import *

class TweetGrabber():
	
	def __init__(self,myApi,sApi,at,sAt):
		self.tweepy = tweepy
		auth = tweepy.OAuthHandler(myApi, sApi)
		auth.set_access_token(at, sAt)
		self.api = tweepy.API(auth, wait_on_rate_limit=True)
		
	#Return the string without non ASCII characters
	def strip_non_ascii(self,string):
		
		stripped = (c for c in string if 0 < ord(c) < 127)
		return ''.join(stripped)  
		
	def user_search(self,user,csv_prefix):
		API_results = self.tweepy.Cursor(self.api.user_timeline,screen_name=user,tweet_mode='extended').items()

		with open(f'{csv_prefix}.csv', 'w', newline='') as csvfile:
			fieldnames = ['tweet_id', 'tweet_text', 'date', 'user_id', 'user_mentions', 'retweet_count']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			writer.writeheader()

			for tweet in API_results:
				text = self.strip_non_ascii(tweet.full_text)
				date = tweet.created_at.strftime('%m/%d/%Y')        
				writer.writerow({
								'tweet_id': tweet.id_str,
								'tweet_text': text,
								'date': date,
								'user_id': tweet.user.id_str,
								'user_mentions':tweet.entities['user_mentions'],
								'retweet_count': tweet.retweet_count
								})

# Process the created CSV in order to generate edge list
class RetweetParser():
	
	def __init__(self,data,user):
		self.user = user

		edge_list = []
	
		for idx,row in data.iterrows():
			if len(row[4]) > 5:    
				user_account = user
				weight = np.log(row[5] + 1)
				for idx_1, item in enumerate(ast.literal_eval(row[4])):
					edge_list.append((user_account,item['screen_name'],weight))

					for idx_2 in range(idx_1+1,len(ast.literal_eval(row[4]))):
						name_a = ast.literal_eval(row[4])[idx_1]['screen_name']
						name_b = ast.literal_eval(row[4])[idx_2]['screen_name']

						edge_list.append((name_a,name_b,weight))
		
		with open(f'{self.user}.csv', 'w', newline='') as csvfile:
			fieldnames = ['user_a', 'user_b', 'log_retweet']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
			writer.writeheader()

			for row in edge_list:        
				writer.writerow({
								'user_a': row[0],
								'user_b': row[1],
								'log_retweet': row[2]
								})


# Eigenvector centrality measures 'influence' of each node within the graph network
class TweetGraph():
	def __init__(self,edge_list):
		data = pd.read_csv(edge_list).to_records(index=False)
		self.tuple_graph = igraph.Graph.TupleList(data, weights=True, directed=False)
		
	def e_centrality(self):
		vectors = self.tuple_graph.eigenvector_centrality()
		e = {name:cen for cen, name in  zip([v for v in vectors],self.tuple_graph.vs['name'])}
		return sorted(e.items(), key=operator.itemgetter(1),reverse=True)