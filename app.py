import os
import requests
import json
import random

from flask import abort, Flask, config, jsonify, request, json, render_template, Response, make_response, g
from flask_apscheduler import APScheduler
from pornhub_api import PornhubApi
from flask_caching import Cache

url = "https://icanhazdadjoke.com/"
headers = {
    "Accept": "application/json"
}

subreddit = 'buildapcsales'
limit = 5
timeframe = 'all' #hour, day, week, month, year, all
listing = 'new' # controversial, best, hot, new, random, rising, top
postToken = os.environ['buildapc_postToken']
debug = os.environ['debug']
print(f'Debug: {debug}\nToken: {postToken}')
slack_url = "https://hooks.slack.com/services/" + postToken
app = Flask(__name__)

# initialize and start the flask app scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# configure and initilize the memory based cache
cacheConfig = {
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DEFAULT_TIMEOUT": 3600,
    "CACHE_DIR": "/tmp"
}
cache = Cache()
cache.init_app(app=app, config=cacheConfig)

# put an emptyList in the cache entry named "latest_list"
emptyList = {}
cache.set("latest_list", emptyList, timeout=0)

# get a reddit post from a subreddit and return a dict indexed on id with:
#   title
#   url
#   flair
def get_reddit(subreddit,listing,limit,timeframe):
    response = {}

    try:
        base_url = f'https://www.reddit.com/r/{subreddit}/{listing}.json?limit={limit}&t={timeframe}'
        # print(base_url)
        request = requests.get(base_url, headers = {'User-agent': 'slackbot/dadjokes'})
    except:
        print('An Error Occured')
    r = request.json()
 
    #print(r)

    for post in r['data']['children']:
        title = post['data']['title']
        id = post['data']['id'].strip()
        url = post['data']['url']
        flair = post['data']['link_flair_richtext'][0]['t']

        # if the post is considered expired or is a meta post, skip it
        if flair.strip().lower() == "expired" or flair.strip().lower() == "meta":
            continue

        response[id] = { 
            'title': title,
            'url': url,
            'flair': flair
        }

    return response

# returns a dict that is a valid slack block object
def format_post(r):
    rDict = {
        "blocks": []
    }

    for id in r:
        title = r[id]['title']
        url = r[id]['url']
        flair = r[id]['flair']
        rDict['blocks'].append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{title} | {url}"
                }
            }
        )
        
    return(rDict)

# returns the difference between 2 dicts. If the new one is empty then it returns the current one
def diff(current, new):
    output = {}

    if debug == "1":
        print("Current is: ")
        simple_print(current)
        print("")

        print("New is: ")
        simple_print(new)
        print("")

    if len(new) == 0:
        output = current
    else:
        for key in new:
            if key not in current:
                print(f"Found a new item [{key}]")
                output[key] = new[key]
    
    return output

# debugging printing
# prints out in a readable format instead of raw dict output
def simple_print(r):
    for id in r:
        title = r[id]['title']
        url = r[id]['url']
        flair = r[id]['flair']
        print(f"[{id}] {title} [{url}] [{flair}]")

def is_request_valid(request):
    is_token_valid = request.form['token'] in os.environ['token'].split(',')
    is_team_id_valid = request.form['team_id'] in os.environ['team'].split(',')

#    print(request.form)
    
    return is_token_valid and is_team_id_valid

@app.route('/dadjoke', methods=['POST'])
def dadjoke():
    if not is_request_valid(request):
        abort(400)

    r = requests.get(url=url, headers=headers)

    if ( r.status_code == 200 ):
        resp = r.json()['joke']
    else:
        resp = "Something went wrong!"
        
    return jsonify(
        response_type='in_channel',
        text=resp
    )

@app.route('/nsfp', methods=['POST'])
def phub():
    if not is_request_valid(request):
        abort(400)

    api = PornhubApi()

    if request.form['text'] is not None:
        search=request.form['text']
    else:
        search="tits"

    results = api.search.search(q=search, ordering="featured", thumbsize="large_hd")
    vid = random.choice(results.videos)
    thumbnail = random.choice(vid.thumbs)

    # If we got back both the title, image url, and video url, then we are good to go
    if vid is not None:
        if vid.title is not None and thumbnail.src is not None and vid.url is not None:
            resp = True
    else:
        resp = False

    # If the response was valid then create an slack block API response with the image, title, and a link to the video
    if resp is True:
        rDict = {
            "blocks": [
                {
                    "type": "image",
                    "image_url": str(thumbnail.src),
                    "alt_text": vid.title
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "{title} | {url}".format(title=vid.title, url=str(vid.url))
                        }
                    ]
                }
            ],
            "response_type": "in_channel"
        }
    # otherwise respond with an error message
    else:
        rDict = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Something went wrong!"
                    }
                }
            ]
        }

#    print("test: [{}]".format(rDict))
    
    return rDict

@app.route('/', methods=['GET'])
def slash():
    return "<html><a href=\"https://github.com/linkages/dadjokes\">Dad jokes repo</a></html>"

@scheduler.task('interval', id='reddit', seconds=120, misfire_grace_time=900)
def reddit():
    # get the latest list from the cache
    latest_list = cache.get("latest_list")
    # make a request to reddit to get the lastest items
    new_request = get_reddit(subreddit,listing,limit,timeframe)
    if debug == "1":
        print("Newist list is:")
        simple_print(new_request)
    
    # Calculate the difference between the new request and the latest cache list
    difference = diff(current=latest_list, new=new_request)
    
    if debug == "1":
        print("Difference is:")
        simple_print(difference)
        print("")

    # If the size of the difference dict is zero then nothing changed since we last checked
    # lets just remove the cache entry and refresh it
    if len(difference) == 0:
        print("Nothing new to post")
        cache.delete("latest_list")
        cache.set("latest_list", new_request, timeout=0)
    else:
        # Something is different
        print("Found some new stuff and updating the cache")
        # set the local latest_list to the new items
        latest_list = new_request
        # delete the cache
        cache.delete("latest_list")
        # update the cache
        cache.set("latest_list", latest_list, timeout=0)
        #print("Would post the following:")
        #simple_print(latest_list)
        #print("")
        # create a slack block post dict using just the differences
        post = format_post(difference)
        # print(post)
        # Set appropriate headers and post to slack
        headers = {'Content-type': 'application/json'}
        response = requests.post(slack_url, headers=headers, data=json.dumps(post))
        #print(response)