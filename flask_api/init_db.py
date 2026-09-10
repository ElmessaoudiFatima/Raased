from app import create_app

app = create_app()

with app.app_context():
    print("Base de données initialisée avec succès.")