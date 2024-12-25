from flask import jsonify, request
from flask_restful import Resource, Api
from flask_login import current_user
from functools import wraps
import jwt
from datetime import datetime, timedelta
from app import app, db
from models import User, Channel, Playlist, Program, Favorite

api = Api(app)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return {'message': 'Token manquant'}, 401
            
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except:
            return {'message': 'Token invalide'}, 401
            
        return f(current_user, *args, **kwargs)
    return decorated

class AuthAPI(Resource):
    def post(self):
        data = request.get_json()
        
        user = User.query.filter_by(username=data.get('username')).first()
        if user and user.check_password(data.get('password')):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, app.config['JWT_SECRET_KEY'])
            
            return {
                'token': token,
                'user_id': user.id,
                'username': user.username
            }
            
        return {'message': 'Identifiants invalides'}, 401

class ChannelListAPI(Resource):
    @token_required
    def get(current_user):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        category = request.args.get('category')
        
        query = Channel.query
        if category:
            query = query.filter_by(category=category)
            
        channels = query.paginate(page=page, per_page=per_page)
        
        return {
            'channels': [{
                'id': c.id,
                'name': c.name,
                'url': c.url,
                'logo': c.logo,
                'category': c.category,
                'is_favorite': bool(Favorite.query.filter_by(
                    user_id=current_user.id,
                    channel_id=c.id
                ).first())
            } for c in channels.items],
            'total': channels.total,
            'pages': channels.pages,
            'current_page': channels.page
        }

class ChannelAPI(Resource):
    @token_required
    def get(current_user, channel_id):
        channel = Channel.query.get_or_404(channel_id)
        current_program = Program.query.filter(
            Program.channel_id == channel_id,
            Program.start_time <= datetime.utcnow(),
            Program.end_time >= datetime.utcnow()
        ).first()
        
        next_programs = Program.query.filter(
            Program.channel_id == channel_id,
            Program.start_time >= datetime.utcnow()
        ).limit(5).all()
        
        return {
            'id': channel.id,
            'name': channel.name,
            'url': channel.url,
            'logo': channel.logo,
            'category': channel.category,
            'current_program': {
                'title': current_program.title,
                'description': current_program.description,
                'start_time': current_program.start_time.isoformat(),
                'end_time': current_program.end_time.isoformat()
            } if current_program else None,
            'next_programs': [{
                'title': p.title,
                'start_time': p.start_time.isoformat(),
                'end_time': p.end_time.isoformat()
            } for p in next_programs]
        }

class PlaylistAPI(Resource):
    @token_required
    def get(current_user):
        playlists = Playlist.query.filter_by(user_id=current_user.id).all()
        return {
            'playlists': [{
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'channel_count': p.channels.count(),
                'last_updated': p.last_updated.isoformat()
            } for p in playlists]
        }
        
    @token_required
    def post(current_user):
        data = request.get_json()
        
        playlist = Playlist(
            name=data['name'],
            url=data['url'],
            description=data.get('description', ''),
            user_id=current_user.id
        )
        
        db.session.add(playlist)
        db.session.commit()
        
        # Lancer la tâche de mise à jour en arrière-plan
        from tasks import update_playlist
        update_playlist.delay(playlist.id)
        
        return {
            'message': 'Playlist créée avec succès',
            'playlist_id': playlist.id
        }, 201

class FavoriteAPI(Resource):
    @token_required
    def post(current_user, channel_id):
        if not Favorite.query.filter_by(
            user_id=current_user.id,
            channel_id=channel_id
        ).first():
            favorite = Favorite(user_id=current_user.id, channel_id=channel_id)
            db.session.add(favorite)
            db.session.commit()
            
        return {'message': 'Chaîne ajoutée aux favoris'}
        
    @token_required
    def delete(current_user, channel_id):
        Favorite.query.filter_by(
            user_id=current_user.id,
            channel_id=channel_id
        ).delete()
        db.session.commit()
        return {'message': 'Chaîne retirée des favoris'}

class SearchAPI(Resource):
    @token_required
    def get(current_user):
        query = request.args.get('q', '')
        
        channels = Channel.query.filter(
            Channel.name.ilike(f'%{query}%')
        ).limit(20).all()
        
        programs = Program.query.filter(
            Program.title.ilike(f'%{query}%')
        ).limit(20).all()
        
        return {
            'channels': [{
                'id': c.id,
                'name': c.name,
                'logo': c.logo,
                'category': c.category
            } for c in channels],
            'programs': [{
                'id': p.id,
                'title': p.title,
                'channel': p.channel.name,
                'start_time': p.start_time.isoformat(),
                'end_time': p.end_time.isoformat()
            } for p in programs]
        }

# Enregistrement des routes API
api.add_resource(AuthAPI, '/api/auth')
api.add_resource(ChannelListAPI, '/api/channels')
api.add_resource(ChannelAPI, '/api/channels/<int:channel_id>')
api.add_resource(PlaylistAPI, '/api/playlists')
api.add_resource(FavoriteAPI, '/api/favorites/<int:channel_id>')
api.add_resource(SearchAPI, '/api/search')
