import os
import requests
import json

from flask import abort, Flask, jsonify, request

app = Flask(__name__)
url="https://icanhazdadjoke.com/"
headers = {
    "Accept": "application/json"
}

def is_request_valid(request):
    is_token_valid = request.form['token'] == os.environ['token']
    is_team_id_valid = request.form['team_id'] == os.environ['team']
    
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

@app.route('/', methods=['GET'])
def slash():
    return "<html><a href="https://github.com/linkages/dadjokes">Dad jokes repo</a></html>"
