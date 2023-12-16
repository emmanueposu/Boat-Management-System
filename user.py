from flask import Blueprint, request
from google.cloud import datastore
import json
import constants

bp = Blueprint('user', __name__, url_prefix='/users')

client = datastore.Client()


@bp.get('')
def users_get():
    if 'application/json' not in request.accept_mimetypes:
        return (json.dumps({}), 406)
    query = client.query(kind=constants.users)
    results = list(query.fetch())
    return (json.dumps(results), 200)
