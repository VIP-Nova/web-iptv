from app import db
from datetime import datetime

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    original_title = db.Column(db.String(200))
    description = db.Column(db.Text)
    release_date = db.Column(db.Date)
    duration = db.Column(db.Integer)  # en minutes
    poster = db.Column(db.String(500))
    backdrop = db.Column(db.String(500))
    rating = db.Column(db.Float)
    tmdb_id = db.Column(db.Integer, unique=True)
    imdb_id = db.Column(db.String(20), unique=True)
    quality = db.Column(db.String(20))  # SD, HD, FHD, 4K
    stream_url = db.Column(db.String(500))
    trailer_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    
    # Relations
    genres = db.relationship('Genre', secondary='movie_genres')
    actors = db.relationship('Actor', secondary='movie_actors')
    directors = db.relationship('Director', secondary='movie_directors')

class Series(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    original_title = db.Column(db.String(200))
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(50))  # En cours, Terminée, Annulée
    poster = db.Column(db.String(500))
    backdrop = db.Column(db.String(500))
    rating = db.Column(db.Float)
    tmdb_id = db.Column(db.Integer, unique=True)
    imdb_id = db.Column(db.String(20), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_views = db.Column(db.Integer, default=0)
    
    # Relations
    seasons = db.relationship('Season', backref='series', lazy=True)
    genres = db.relationship('Genre', secondary='series_genres')
    actors = db.relationship('Actor', secondary='series_actors')
    creators = db.relationship('Creator', secondary='series_creators')

class Season(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    overview = db.Column(db.Text)
    poster = db.Column(db.String(500))
    air_date = db.Column(db.Date)
    episode_count = db.Column(db.Integer)
    
    # Relations
    episodes = db.relationship('Episode', backref='season', lazy=True)

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    air_date = db.Column(db.Date)
    duration = db.Column(db.Integer)  # en minutes
    still = db.Column(db.String(500))  # image de l'épisode
    stream_url = db.Column(db.String(500))
    quality = db.Column(db.String(20))
    views = db.Column(db.Integer, default=0)

class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)

class Actor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.String(500))
    biography = db.Column(db.Text)
    birth_date = db.Column(db.Date)
    tmdb_id = db.Column(db.Integer, unique=True)

class Director(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.String(500))
    biography = db.Column(db.Text)
    tmdb_id = db.Column(db.Integer, unique=True)

class Creator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.String(500))
    biography = db.Column(db.Text)
    tmdb_id = db.Column(db.Integer, unique=True)

# Tables de liaison
movie_genres = db.Table('movie_genres',
    db.Column('movie_id', db.Integer, db.ForeignKey('movie.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genre.id'), primary_key=True)
)

series_genres = db.Table('series_genres',
    db.Column('series_id', db.Integer, db.ForeignKey('series.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genre.id'), primary_key=True)
)

movie_actors = db.Table('movie_actors',
    db.Column('movie_id', db.Integer, db.ForeignKey('movie.id'), primary_key=True),
    db.Column('actor_id', db.Integer, db.ForeignKey('actor.id'), primary_key=True),
    db.Column('role', db.String(200))
)

series_actors = db.Table('series_actors',
    db.Column('series_id', db.Integer, db.ForeignKey('series.id'), primary_key=True),
    db.Column('actor_id', db.Integer, db.ForeignKey('actor.id'), primary_key=True),
    db.Column('role', db.String(200))
)

movie_directors = db.Table('movie_directors',
    db.Column('movie_id', db.Integer, db.ForeignKey('movie.id'), primary_key=True),
    db.Column('director_id', db.Integer, db.ForeignKey('director.id'), primary_key=True)
)

series_creators = db.Table('series_creators',
    db.Column('series_id', db.Integer, db.ForeignKey('series.id'), primary_key=True),
    db.Column('creator_id', db.Integer, db.ForeignKey('creator.id'), primary_key=True)
)

# Modèles pour les fonctionnalités sociales et de personnalisation
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(50))  # 'movie' ou 'series'
    content_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(50))  # 'movie' ou 'series'
    content_id = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(50))  # 'movie', 'episode'
    content_id = db.Column(db.Integer, nullable=False)
    progress = db.Column(db.Float)  # pourcentage de visionnage
    last_watched = db.Column(db.DateTime, default=datetime.utcnow)

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(50))
    content_id = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float)  # score de recommandation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Collection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    poster = db.Column(db.String(500))
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class CollectionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('collection.id'), nullable=False)
    content_type = db.Column(db.String(50))
    content_id = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer)
