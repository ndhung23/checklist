from app import create_app
from models import db


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("Database initialized.")
