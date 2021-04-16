import os
import requests
import json
import random

from flask import abort, Flask, jsonify, request, json, render_template, Response, make_response
from pornhub_api import PornhubApi

app = Flask(__name__)
url="https://icanhazdadjoke.com/"
headers = {
    "Accept": "application/json"
}

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
