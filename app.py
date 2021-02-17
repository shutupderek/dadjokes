import os
import requests
import json
import random

from flask import abort, Flask, jsonify, request
from pornhub_api import PornhubApi

from slack_blockkit.composition_object import TextObject
from slack_blockkit.layout_block import DividerBlock, ImageBlock
from slack_blockkit.utils import get_blocks

app = Flask(__name__)
url="https://icanhazdadjoke.com/"
headers = {
    "Accept": "application/json"
}

def is_request_valid(request):
    is_token_valid = request.form['token'] == os.environ['token']
    is_team_id_valid = request.form['team_id'] == os.environ['team']

    print(request.form)
    
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
        search="boobs"

    results = api.search.search(q=search, ordering="featured", thumbsize="large_hd")
    vid = random.choice(results.videos)
    thumbnail = random.choice(vid.thumbs)

    if vid is not None:
        if vid.title is not None and thumbnail.src is not None and vid.url is not None:
            resp = "{title} | {link} | {thumbnail}".format(title=vid.title, link=vid.url, thumbnail=thumbnail.src)
    else:
        resp = "No response"

    debug = jsonify(response_type='in_channel', text=resp)
    print(debug)
        
    return jsonify(
        response_type='in_channel',
        text=resp
    )

@app.route('/', methods=['GET'])
def slash():
    return "<html><a href=\"https://github.com/linkages/dadjokes\">Dad jokes repo</a></html>"
