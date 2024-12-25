from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    profile_image = db.Column(db.String(200))
    
    # Relations
    playlists = db.relationship('Playlist', backref='owner', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='user', lazy='dynamic')
    watchlist = db.relationship('WatchlistItem', backref='user', lazy='dynamic')
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relations
    channels = db.relationship('Channel', backref='playlist', lazy='dynamic')
    
class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    logo = db.Column(db.String(500))
    category = db.Column(db.String(100))
    language = db.Column(db.String(50))
    country = db.Column(db.String(50))
    epg_id = db.Column(db.String(100))
    is_adult = db.Column(db.Boolean, default=False)
    is_radio = db.Column(db.Boolean, default=False)
    quality = db.Column(db.String(20))  # SD, HD, FHD, 4K
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    
    # Relations
    programs = db.relationship('Program', backref='channel', lazy='dynamic')
    favorites = db.relationship('Favorite', backref='channel', lazy='dynamic')

class Program(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    category = db.Column(db.String(100))
    thumbnail = db.Column(db.String(500))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False)
    notify = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.String(50), nullable=False)  # basic, premium, family
    status = db.Column(db.String(20), nullable=False)  # active, cancelled, expired
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    stripe_subscription_id = db.Column(db.String(100))
    auto_renew = db.Column(db.Boolean, default=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(200))
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    
    # Relations
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # login, view_channel, add_playlist, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.JSON)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(500))
    
    __table_args__ = (db.UniqueConstraint('user_id', 'key', name='unique_user_setting'),)
