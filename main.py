from flask import Flask, render_template, session
import boat
import load
import user
import auth0
import json
from os import environ as env
from dotenv import find_dotenv, load_dotenv

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")

app.register_blueprint(boat.bp)
app.register_blueprint(load.bp)
app.register_blueprint(user.bp)
app.register_blueprint(auth0.bp)


@app.route('/')
def index():
    return render_template("home.html", session=session.get('user'),
                           pretty=json.dumps(session.get('user'), indent=4))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
