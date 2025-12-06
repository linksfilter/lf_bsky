from atproto import Client, models
import tweepy
from datetime import datetime, timezone
import json
#import opengraph_py3
from functools import cache
import requests
from tqdm import tqdm
from newspaper import Article, Config
import pandas as pd
import re
import os

#initialize tqdm for apply_progress
tqdm.pandas()

#set variables
BLACKLIST_PATH = 'blacklist.csv'
PARSED_PATH = 'parsed.csv'
POSTED_PATH = 'posted.csv'
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

#set share threshhold for reposting
THRESH = 5

#load bluesky user data
BSKY_USER= os.environ['BSKY_USER']
BSKY_PASS= os.environ['BSKY_PASS']


#set up bluesky client
BSKY_CLIENT = Client()
profile = BSKY_CLIENT.login(BSKY_USER, BSKY_PASS)

#load twitter user data
CONSUMER_KEY=os.environ['CONSUMER_KEY']
CONSUMER_SECRET=os.environ['CONSUMER_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']

#set up twitter client
TW_CLIENT = tweepy.Client(
    consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
)


#load domain blacklist
with open(BLACKLIST_PATH) as f:
    BLACKLIST = [line.rstrip() for line in f]

#load dataframe of links that have already been parsed
PARSED_DF = pd.read_csv(PARSED_PATH, engine="python", on_bad_lines='skip').dropna(subset='uri').drop_duplicates(subset='uri')

#load links that were already posted
with open(POSTED_PATH) as f:
    OLDLIST = [line.rstrip() for line in f]

#define current time
NOW = datetime.now(timezone.utc)

#gets a dataframe of the bluesky user's timeline, iterates until it has 7 days or the cursor is set to None
def get_bsky_posts(cursor=NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),days = 7):
  delta = NOW-NOW
  data = []
  while delta.days <days:
    response = BSKY_CLIENT.get_timeline(cursor=cursor).json()
    posts = json.loads(response)
    data = data+[post['post'] for post in posts['feed']]
    cursor = posts['cursor']
    if cursor is None:
        break
    try:
      timestamp = datetime.strptime(posts['cursor'],"%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except:
      timestamp = datetime.strptime(posts['cursor'],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    delta = NOW-timestamp
    #print(delta.days)
  df = pd.DataFrame(data)
  return df

def generate_facets_from_links_in_text(text):
    ''' Based on logic in
        https://github.com/GanWeaving/social-cross-post/blob/main/helpers.py

        Generate atproto facets for each URL in the text
    '''
    facets = []
    for match in URL_PATTERN.finditer(text):
        facets.append(gen_link(*match.span(), match.group(0)))
    return facets

def gen_link(start, end, uri):
    ''' Return a dict defining start + end character along
    with the type of the facet and where it should link to.

    We're literally saying "characters 4-12" are a link which
    should point to foo
    '''
    return {
        "index": {
            "byteStart": start+8,
            "byteEnd": end+8
        },
        "features": [{
            "$type": "app.bsky.richtext.facet#link",
            "uri": uri
        }]
    }

def create_bsky_linkpost(title,description,link,image):
    ''' Post into Bluesky
    '''
    try:
        text = f"{description} {link}"

        # Identify links and generate AT facets so that they act as links
        facets = generate_facets_from_links_in_text(text)

        # Create a short description for the preview card
        short_desc = ''
        thumb = None

        # See whether there's a thumbnail defined
        if image is not None and image != 'None':
            # fetch it
            response = requests.get(image)
            img_data = response.content

            # Upload the image
            upload = BSKY_CLIENT.com.atproto.repo.upload_blob(img_data)
            thumb = upload.blob

        # Create a link card embed
        embed_external = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=title,
                description=short_desc,
                uri=link,
                thumb=thumb
            )
        )

        # Submit the post
        BSKY_CLIENT.com.atproto.repo.create_record(
            models.ComAtprotoRepoCreateRecord.Data(
                repo=BSKY_CLIENT.me.did,
                collection='app.bsky.feed.post',
                record=models.AppBskyFeedPost.Record(
                createdAt=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z",
                text=f"{description} {link}",
                embed=embed_external,
                facets=facets
                ),
            )
        )
        print(text)
        return True
    except Exception as e:
        print(f"Failed to post to Bluesky: {e}")
        return False

@cache
def enrich_link_lw(link):
    print(link)
    try:
      api_url="https://opengraph.lewagon.com/"
      params= {'url':link}
      response = requests.get(api_url,params=params, timeout=5).json()
      print(response)
      try:
        title = response['data']['title'].replace('*',':')
      except:
        title = ''
      try:
        description = response['data']['description'].replace('*',':')
      except:
        if title !='':
          description = title
        else:
          description = ''
      try:
        new_link = response['data']['url']
      except:
        new_link = link
      return title, description, new_link
    except:
      return 'error','error','error'

@cache
def enrich_link_np(link):
    print(link)
    config = Config()
    config.request_timeout = 10
    try:
        article = Article(link, config=config)
        article.download()
        article.parse()
        # Use canonical_link if available
        new_link = article.canonical_link or link
        # Extract title, description, and publish_date
        title = article.title.replace('*', ':') if article.title else ''
        description = article.meta_description.replace('*', ':') if article.meta_description else title
        # Use publish_date if available
        date = article.publish_date.strftime("%Y-%m-%d") if article.publish_date else ''
    except Exception as e:
        print(f"Error parsing {link}: {e}")
        title, description, new_link, date = 'error', 'error', link, ''
    return title, description, new_link, date

@cache
def enrich_link_og(link):
    try:
      data = opengraph_py3.OpenGraph(url=link, timeout=5)
    except:
      return 'error','error','error'
    try:
      title = data['title'].replace('*',':')
    except:
      title = ''
    try:
      description = data['description'].replace('*',':')
    except:
      if title !='':
        description = title
      else:
        description = ''
    try:
      new_link = data['url']
    except:
      new_link = link
    return title, description, new_link

@cache
def enrich_link(link):
    print(link)
    title, description, new_link, date = enrich_link_np(link)
    # fallback parsers (optional)
    # if title == 'error': title, description, new_link, date = enrich_link_og(link)
    # if title == 'error': title, description, new_link, date = enrich_link_lw(link)
    return title, description, new_link, date

if __name__ == "__main__":
  #get bluesky timeline
  bsky_df = get_bsky_posts(days=3)

  #extract post type
  bsky_df['type'] = bsky_df['embed'].apply(lambda x: list(x.keys())[0] if x is not None else None)

  #make a list of all posts with an embedded article
  links = bsky_df[bsky_df['type']=='external']['embed'].to_list()

  #create a list of dictionaries of those articles and convert to dataframe
  data = [post['external'] for post in links]
  links_df = pd.DataFrame(data)

  #remove links that are from blacklisted domains
  pattern ='|'.join(BLACKLIST)
  links_df = links_df[~(links_df['uri'].str.lower().str.contains(pattern))]

  #add parsed data and parse data for unknown links
  links_df = links_df.merge(PARSED_DF[['uri','titel','beschreibung','link']],on='uri',how='left')
  filled_links = links_df[links_df['link'].notna()].copy()
  missing_links = links_df[links_df['link'].isna()].copy()
  print(list(missing_links['uri'].unique()))
  missing_links['titel'],missing_links['beschreibung'],missing_links['link'],missing_links['date'] = zip(*missing_links['uri'].progress_apply(enrich_link))
  links_df = pd.concat([filled_links,missing_links])

  #fill empty cells
  links_df['titel'] =  links_df.apply(lambda x: x['title'] if x['titel'] == '' else x['titel'],axis=1).fillna('')
  links_df['link'] =  links_df.apply(lambda x: x['uri'] if x['link'] == '' else x['link'],axis=1).fillna('')
  links_df['beschreibung'] =  links_df.apply(lambda x: x['description'] if x['beschreibung'] is None else x['titel'],axis=1)

  #update parsed data
  NEW_PARSED = pd.concat([PARSED_DF, missing_links]).drop_duplicates(subset='uri').tail(10000)
  NEW_PARSED.to_csv(PARSED_PATH, index=False)

  #evaluate top links
  toplinks = links_df.groupby('link').count().sort_values('description',ascending=False)
  toplinks =  toplinks[toplinks['description']>=THRESH]
  linkliste= [link for link in toplinks.index.to_list() if link !='']

  #filter out only links that have not yet been posted
  new_links = [link for link in linkliste if link not in OLDLIST]

  #if there is more than one new link, post them and save to file
  if len(new_links)>0:
    new_list = OLDLIST+new_links
    with open(POSTED_PATH, mode='w') as f:
        f.write("\n".join(new_list) + "\n")
    for link in new_links:
      print('posting '+link)
      create_bsky_linkpost(links_df[links_df['link']==link].iloc[0]['titel'],links_df[links_df['link']==link].iloc[0]['beschreibung'],links_df[links_df['link']==link].iloc[0]['link'],links_df[links_df['link']==link].iloc[0]['thumb'])
      print('posted to bluesky')
      try:
        TW_CLIENT.create_tweet(text=f"{links_df[links_df['link']==link].iloc[0]['beschreibung']} {links_df[links_df['link']==link].iloc[0]['link']}")
        print('posted to twitter')
      except:
        print('could not post to twitter')

  #finished
  print('linksfilter done')
