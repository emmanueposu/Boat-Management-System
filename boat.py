from flask import Blueprint, request
from google.cloud import datastore
import json
import constants

bp = Blueprint('boat', __name__, url_prefix='/boats')

client = datastore.Client()


@bp.route('', methods=['POST', 'GET'])
def boats_post_get():
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    elif request.method == 'POST':
        content = request.get_json()
        new_boat = datastore.entity.Entity(key=client.key(constants.boats))
        new_boat.update({'name': content['name'],
                         'type': content['type'],
                         'length': content['length'],
                         'loads': []})
        client.put(new_boat)
        new_boat['id'] = new_boat.key.id
        new_boat['self'] = request.url + '/' + str(new_boat.key.id)
        return (json.dumps(new_boat), 201)
    elif request.method == 'GET':
        query = client.query(kind=constants.boats)
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
        for boat in results:
            boat['id'] = boat.key.id
            boat['self'] = request.url_root + 'boats/' + str(boat.key.id)
            for load in boat['loads']:
                load['self'] = request.url_root + 'loads/' + str(load['id'])
        output = {'boats': results,
                  'total': len(results)}
        if next_url:
            output["next"] = next_url
        return (json.dumps(output), 200)
    else:
        return (json.dumps({}), 405)


@bp.get('/<id>')
def boats_get(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    boat_key = client.key(constants.boats, int(id))
    boat = client.get(key=boat_key)
    if boat is None:
        error = {"Error": "No boat with this boat_id exists"}
        return (json.dumps(error), 404)
    boat['id'] = boat.key.id
    boat['self'] = request.url
    for load in boat['loads']:
        load['self'] = request.url_root + 'loads/' + str(load['id'])
    return (json.dumps(boat), 200)


@bp.route('/<id>', methods=['PATCH', 'PUT'])
def boats_patch_put(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    boat_key = client.key(constants.boats, int(id))
    boat = client.get(key=boat_key)
    if boat is None:
        error = {"Error": "No boat with this boat_id exists"}
        return (json.dumps(error), 404)
    content = request.get_json()
    for key in content:
        if key != 'loads':
            boat[key] = content[key]
    client.put(boat)
    boat['id'] = boat.key.id
    boat['self'] = request.url
    for load in boat['loads']:
        load['self'] = request.url_root + 'loads/' + str(load['id'])
    return (json.dumps(boat), 200)


@bp.delete('/<id>')
def boats_delete(id):
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    boat_key = client.key(constants.boats, int(id))
    boat = client.get(key=boat_key)
    if boat is None:
        error = {"Error": "No boat with this boat_id exists"}
        return (json.dumps(error), 404)
    query = client.query(kind=constants.loads)
    results = list(query.fetch())
    for load in results:
        if (load['carrier'] is not None and
           load['carrier']['id'] == int(id)):
            load['carrier'] = None
            client.put(load)
            break
    client.delete(boat)
    return (json.dumps({}), 204)
