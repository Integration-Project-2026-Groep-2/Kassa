import logging

from flask import Flask

from api.routes import bp
from db import init_db


def create_app() -> Flask:
    app = Flask(__name__)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  %(name)s  %(levelname)s  %(message)s',
    )

    init_db()
    app.register_blueprint(bp)
    return app
