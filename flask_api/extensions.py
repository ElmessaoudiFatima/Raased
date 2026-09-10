from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cors = CORS()


def init_extensions(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["DATABASE_URL"]
    db.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )