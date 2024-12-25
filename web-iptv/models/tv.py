from app import db
from datetime import datetime

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    logo = db.Column(db.String(500))
    stream_url = db.Column(db.String(500), nullable=False)
    backup_stream_url = db.Column(db.String(500))  # URL de secours
    category = db.Column(db.String(100))
    language = db.Column(db.String(50))
    country = db.Column(db.String(100))
    quality = db.Column(db.String(20))  # SD, HD, FHD, 4K
    epg_id = db.Column(db.String(100))  # Identifiant EPG
    is_active = db.Column(db.Boolean, default=True)
    last_checked = db.Column(db.DateTime)
    is_working = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    programs = db.relationship('Program', backref='channel', lazy=True)
    categories = db.relationship('ChannelCategory', secondary='channel_categories')

class ChannelCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    icon = db.Column(db.String(500))
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)

class Program(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(100))
    thumbnail = db.Column(db.String(500))
    is_live = db.Column(db.Boolean, default=False)
    rating = db.Column(db.String(10))
    language = db.Column(db.String(50))
    subtitle_languages = db.Column(db.String(200))  # Liste des langues de sous-titres disponibles

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500))  # URL M3U
    local_path = db.Column(db.String(500))  # Chemin local du fichier M3U
    last_updated = db.Column(db.DateTime)
    auto_update = db.Column(db.Boolean, default=True)
    update_interval = db.Column(db.Integer, default=24)  # Intervalle de mise à jour en heures
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EPGSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))  # URL XMLTV
    local_path = db.Column(db.String(500))  # Chemin local du fichier XMLTV
    last_updated = db.Column(db.DateTime)
    auto_update = db.Column(db.Boolean, default=True)
    update_interval = db.Column(db.Integer, default=12)  # Intervalle de mise à jour en heures
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Tables de liaison
channel_categories = db.Table('channel_categories',
    db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('channel_category.id'), primary_key=True)
)

# Modèle pour le cache des flux
class StreamCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    quality = db.Column(db.String(20))
    bandwidth = db.Column(db.Integer)  # Bande passante en bits/s
    resolution = db.Column(db.String(20))  # ex: 1920x1080
    codec = db.Column(db.String(50))  # ex: H.264, HEVC
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, default=datetime.utcnow)
    is_working = db.Column(db.Boolean, default=True)

# Modèle pour les statistiques de visionnage
class ViewingStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hour = db.Column(db.Integer, nullable=False)  # Heure de la journée (0-23)
    views = db.Column(db.Integer, default=0)
    average_duration = db.Column(db.Integer, default=0)  # Durée moyenne de visionnage en secondes
    quality_stats = db.Column(db.JSON)  # Statistiques de qualité {quality: count}
    error_count = db.Column(db.Integer, default=0)

# Modèle pour la gestion des régions et des restrictions
class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country_code = db.Column(db.String(2), nullable=False)
    allowed_channels = db.relationship('Channel', secondary='region_channels')

region_channels = db.Table('region_channels',
    db.Column('region_id', db.Integer, db.ForeignKey('region.id'), primary_key=True),
    db.Column('channel_id', db.Integer, db.ForeignKey('channel.id'), primary_key=True)
)
