from app import app, db
from models import *

def init_db():
    with app.app_context():
        # Création des tables
        db.create_all()
        
        # Création des catégories par défaut
        default_categories = [
            'Sports',
            'News',
            'Movies',
            'Series',
            'Kids',
            'Music',
            'Documentary'
        ]
        
        for category_name in default_categories:
            if not ChannelCategory.query.filter_by(name=category_name).first():
                category = ChannelCategory(name=category_name)
                db.session.add(category)
        
        db.session.commit()
        print("Base de données initialisée avec succès!")

if __name__ == '__main__':
    init_db()
