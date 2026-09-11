import os

from flask import Flask, jsonify

from admin import admin_bp
from auth import auth_bp
from config import Config
from driver import driver_bp
from extensions import db, init_extensions
from manager import manager_bp
from map_data import map_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    init_extensions(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(map_bp)

    if app.config["AUTO_CREATE_DB"]:
        with app.app_context():
            db.create_all()
            if app.config["AUTO_SEED"]:
                from seed import seed_if_empty

                seed_if_empty()

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="Ressource introuvable."), 404

    @app.errorhandler(500)
    def server_error(_):
        return jsonify(error="Erreur interne du serveur."), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)