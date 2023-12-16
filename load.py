from flask import Blueprint, request, jsonify
from google.cloud import datastore
from six.moves.urllib.request import urlopen
from jose import jwt
from os import environ as env
from dotenv import load_dotenv, find_dotenv
import json
import constants

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

bp = Blueprint('load', __name__, url_prefix='/loads')

client = datastore.Client()

ALGORITHMS = ["RS256"]


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@bp.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


def verify_jwt(request):
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        token = auth_header[1]
    else:
        raise AuthError({"code": "no auth header",
                         "description":
                         "Authorization header is missing"}, 401)

    jsonurl = (urlopen("https://" + env.get("AUTH0_DOMAIN") +
               "/.well-known/jwks.json"))
    jwks = json.loads(jsonurl.read())
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Invalid header. "
                            "Use an RS256 signed JWT Access Token"}, 401)
    if unverified_header["alg"] == "HS256":
        raise AuthError({"code": "invalid_header",
                        "description":
                            "Invalid header. "
                            "Use an RS256 signed JWT Access Token"}, 401)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=env.get("AUTH0_CLIENT_ID"),
                issuer="https://" + env.get("AUTH0_DOMAIN") + "/"
            )
        except jwt.ExpiredSignatureError:
            raise AuthError({"code": "token_expired",
                            "description": "token is expired"}, 401)
        except jwt.JWTClaimsError:
            raise AuthError({"code": "invalid_claims",
                            "description":
                                "incorrect claims,"
                                " please check the audience and issuer"}, 401)
        except Exception:
            raise AuthError({"code": "invalid_header",
                            "description":
                                "Unable to parse authentication"
                                " token."}, 401)

        return payload
    else:
        raise AuthError({"code": "no_rsa_key",
                         "description":
                         "No RSA key in JWKS"}, 401)


@bp.route('', methods=['POST', 'GET'])
def loads_post_get():
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    try:
        payload = verify_jwt(request)
    except AuthError:
        error = {"Error": "Invalid JWT"}
        return (json.dumps(error), 401)
    if request.method == 'POST':
        content = request.get_json()
        new_load = datastore.entity.Entity(key=client.key(constants.loads))
        new_load.update({'volume': content['volume'],
                         'carrier': None,
                         'item': content['item'],
                         'creation_date': content['creation_date'],
                         'owner': payload['sub']})
        client.put(new_load)
        new_load['id'] = new_load.key.id
        new_load['self'] = request.url + '/' + str(new_load.key.id)
        return (json.dumps(new_load), 201)
    elif request.method == 'GET':
        query = client.query(kind=constants.loads)
        query.add_filter('owner', '=', payload['sub'])
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        l_iterator = query.fetch(limit=q_limit, offset=q_offset)
        pages = l_iterator.pages
        results = list(next(pages))
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = (request.url + "?limit=" + str(q_limit) + "&offset=" +
                        str(next_offset))
        else:
            next_url = None
        for load in results:
            load['id'] = load.key.id
            load['self'] = request.url_root + 'loads/' + str(load.key.id)
            if load['carrier']:
                load['carrier']['self'] = (request.url_root + 'boats/' +
                                           str(load['carrier']['id']))
        output = {'loads': results,
                  'total': len(results)}
        if next_url:
            output["next"] = next_url
        return (json.dumps(output), 200)
    else:
        return (json.dumps({}), 405)


@bp.get('/<id>')
def loads_get(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    load_key = client.key(constants.loads, int(id))
    load = client.get(key=load_key)
    if load is None:
        error = {"Error": "No load with this load_id exists"}
        return (json.dumps(error), 404)
    try:
        payload = verify_jwt(request)
    except AuthError:
        error = {"Error": "Invalid JWT"}
        return (json.dumps(error), 401)
    if load['owner'] != payload['sub']:
        return (json.dumps({}), 401)
    load['id'] = load.key.id
    load['self'] = request.url
    if load['carrier']:
        load['carrier']['self'] = (request.url_root + 'boats/' +
                                   str(load['carrier']['id']))
    return (json.dumps(load), 200)


@bp.route('/<id>', methods=['PATCH', 'PUT'])
def loads_patch_put(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    load_key = client.key(constants.loads, int(id))
    load = client.get(key=load_key)
    if load is None:
        error = {"Error": "No load with this load_id exists"}
        return (json.dumps(error), 404)
    try:
        payload = verify_jwt(request)
    except AuthError:
        error = {"Error": "Invalid JWT"}
        return (json.dumps(error), 401)
    if load['owner'] != payload['sub']:
        return (json.dumps({}), 401)
    content = request.get_json()
    for key in content:
        if key != 'carrier' and key != 'owner':
            load[key] = content[key]
    client.put(load)
    load['id'] = load.key.id
    load['self'] = request.url
    if load['carrier']:
        load['carrier']['self'] = (request.url_root + 'boats/' +
                                   str(load['carrier']['id']))
    return (json.dumps(load), 200)


@bp.delete('/<id>')
def loads_delete(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    load_key = client.key(constants.loads, int(id))
    load = client.get(key=load_key)
    if load is None:
        error = {"Error": "No load with this load_id exists"}
        return (json.dumps(error), 404)
    try:
        payload = verify_jwt(request)
    except AuthError:
        error = {"Error": "Invalid JWT"}
        return (json.dumps(error), 401)
    if load['owner'] != payload['sub']:
        return (json.dumps({}), 401)
    query = client.query(kind=constants.boats)
    results = list(query.fetch())
    idx = None
    for boat in results:
        for i in range(len(boat['loads'])):
            if boat['loads'][i]['id'] == int(id):
                idx = i
                break
        if idx is not None:
            boat['loads'].pop(idx)
            client.put(boat)
            break
    client.delete(load)
    return (json.dumps({}), 204)


@bp.route('/<load_id>/boats/<boat_id>', methods=['PUT', 'DELETE'])
def add_remove_boat(load_id, boat_id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    load_key = client.key(constants.loads, int(load_id))
    load = client.get(key=load_key)
    boat_key = client.key(constants.boats, int(boat_id))
    boat = client.get(key=boat_key)
    if load is None or boat is None:
        error = {"Error": "The specified boat and/or load does not exist"}
        return (json.dumps(error), 404)
    try:
        payload = verify_jwt(request)
    except AuthError:
        error = {"Error": "Invalid JWT"}
        return (json.dumps(error), 401)
    if load['owner'] != payload['sub']:
        return (json.dumps({}), 401)
    if request.method == 'PUT':
        if load['carrier'] is not None:
            error = {"Error": "The load is already loaded on another boat"}
            return (json.dumps(error), 403)
        load['carrier'] = {'id': boat.key.id, 'name': boat['name']}
        boat['loads'].append({'id': load.key.id})
        client.put(load)
        client.put(boat)
        return (json.dumps({}), 204)
    elif request.method == 'DELETE':
        idx = None
        for i in range(len(boat['loads'])):
            if boat['loads'][i]['id'] == int(load_id):
                idx = i
                break
        if idx is not None:
            load['carrier'] = None
            boat['loads'].pop(idx)
            client.put(load)
            client.put(boat)
            return (json.dumps({}), 204)
        error = {"Error": "No boat with this boat_id is loaded with the load" +
                          " with this load_id"}
        return (json.dumps(error), 404)
