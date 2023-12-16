from os import environ as env
from urllib.parse import quote_plus, urlencode
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import redirect, session, url_for, Blueprint, current_app
from google.cloud import datastore
import constants

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

bp = Blueprint('auth0', __name__, url_prefix='/auth0')

client = datastore.Client()

oauth = OAuth(current_app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=(f'https://{env.get("AUTH0_DOMAIN")}/' +
                         '.well-known/openid-configuration')
)


@bp.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("auth0.callback", _external=True)
    )


@bp.route("/callback", methods=["GET", "POST"])
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        visited = False
        for user in results:
            if user['id'] == token['userinfo']['sub']:
                visited = True
                break
        if not visited:
            new_user = datastore.entity.Entity(key=client.key(constants.users))
            new_user['id'] = token['userinfo']['sub']
            client.put(new_user)
        session["user"] = token
        return redirect(url_for("index"))
    except Exception:
        return redirect(url_for("index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("index", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )
