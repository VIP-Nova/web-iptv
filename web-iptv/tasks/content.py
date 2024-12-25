from celery import shared_task
import requests
import logging
from datetime import datetime, timedelta
from app import db, cache
from models.content import Movie, Series, Season, Episode, Actor, Director, Creator, Genre
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

TMDB_API_KEY = 'votre_cle_api_tmdb'
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

@shared_task
def update_movie_metadata(movie_id):
    """Met à jour les métadonnées d'un film depuis TMDB"""
    try:
        movie = Movie.query.get(movie_id)
        if not movie or not movie.tmdb_id:
            return False
            
        # Récupérer les détails du film
        response = requests.get(
            f'{TMDB_BASE_URL}/movie/{movie.tmdb_id}',
            params={
                'api_key': TMDB_API_KEY,
                'language': 'fr-FR',
                'append_to_response': 'credits,videos'
            }
        )
        
        if response.status_code != 200:
            return False
            
        data = response.json()
        
        # Mise à jour des informations de base
        movie.title = data['title']
        movie.original_title = data['original_title']
        movie.description = data['overview']
        movie.release_date = datetime.strptime(data['release_date'], '%Y-%m-%d').date()
        movie.duration = data['runtime']
        movie.poster = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
        movie.backdrop = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
        movie.rating = data['vote_average']
        
        # Mise à jour des genres
        movie.genres = []
        for genre_data in data['genres']:
            genre = Genre.query.filter_by(name=genre_data['name']).first()
            if not genre:
                genre = Genre(name=genre_data['name'])
                db.session.add(genre)
            movie.genres.append(genre)
        
        # Mise à jour des acteurs
        movie.actors = []
        for cast in data['credits']['cast'][:10]:  # Limiter aux 10 premiers acteurs
            actor = Actor.query.filter_by(tmdb_id=cast['id']).first()
            if not actor:
                actor = Actor(
                    name=cast['name'],
                    tmdb_id=cast['id'],
                    photo=f"https://image.tmdb.org/t/p/w185{cast['profile_path']}" if cast['profile_path'] else None
                )
                db.session.add(actor)
            movie.actors.append(actor)
        
        # Mise à jour des réalisateurs
        movie.directors = []
        for crew in data['credits']['crew']:
            if crew['job'] == 'Director':
                director = Director.query.filter_by(tmdb_id=crew['id']).first()
                if not director:
                    director = Director(
                        name=crew['name'],
                        tmdb_id=crew['id'],
                        photo=f"https://image.tmdb.org/t/p/w185{crew['profile_path']}" if crew['profile_path'] else None
                    )
                    db.session.add(director)
                movie.directors.append(director)
        
        # Mise à jour de la bande-annonce
        for video in data['videos']['results']:
            if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                movie.trailer_url = f"https://www.youtube.com/watch?v={video['key']}"
                break
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du film {movie_id}: {str(e)}")
        db.session.rollback()
        return False

@shared_task
def update_series_metadata(series_id):
    """Met à jour les métadonnées d'une série depuis TMDB"""
    try:
        series = Series.query.get(series_id)
        if not series or not series.tmdb_id:
            return False
            
        # Récupérer les détails de la série
        response = requests.get(
            f'{TMDB_BASE_URL}/tv/{series.tmdb_id}',
            params={
                'api_key': TMDB_API_KEY,
                'language': 'fr-FR',
                'append_to_response': 'credits,videos'
            }
        )
        
        if response.status_code != 200:
            return False
            
        data = response.json()
        
        # Mise à jour des informations de base
        series.title = data['name']
        series.original_title = data['original_name']
        series.description = data['overview']
        series.start_date = datetime.strptime(data['first_air_date'], '%Y-%m-%d').date()
        if data['last_air_date']:
            series.end_date = datetime.strptime(data['last_air_date'], '%Y-%m-%d').date()
        series.status = data['status']
        series.poster = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
        series.backdrop = f"https://image.tmdb.org/t/p/original{data['backdrop_path']}"
        series.rating = data['vote_average']
        
        # Mise à jour des genres
        series.genres = []
        for genre_data in data['genres']:
            genre = Genre.query.filter_by(name=genre_data['name']).first()
            if not genre:
                genre = Genre(name=genre_data['name'])
                db.session.add(genre)
            series.genres.append(genre)
        
        # Mise à jour des acteurs
        series.actors = []
        for cast in data['credits']['cast'][:10]:
            actor = Actor.query.filter_by(tmdb_id=cast['id']).first()
            if not actor:
                actor = Actor(
                    name=cast['name'],
                    tmdb_id=cast['id'],
                    photo=f"https://image.tmdb.org/t/p/w185{cast['profile_path']}" if cast['profile_path'] else None
                )
                db.session.add(actor)
            series.actors.append(actor)
        
        # Mise à jour des créateurs
        series.creators = []
        for creator in data['created_by']:
            creator_obj = Creator.query.filter_by(tmdb_id=creator['id']).first()
            if not creator_obj:
                creator_obj = Creator(
                    name=creator['name'],
                    tmdb_id=creator['id'],
                    photo=f"https://image.tmdb.org/t/p/w185{creator['profile_path']}" if creator['profile_path'] else None
                )
                db.session.add(creator_obj)
            series.creators.append(creator_obj)
        
        # Mise à jour des saisons
        for season_data in data['seasons']:
            season = Season.query.filter_by(
                series_id=series.id,
                number=season_data['season_number']
            ).first()
            
            if not season:
                season = Season(
                    series_id=series.id,
                    number=season_data['season_number']
                )
                db.session.add(season)
            
            season.title = season_data['name']
            season.overview = season_data['overview']
            season.poster = f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}"
            season.air_date = datetime.strptime(season_data['air_date'], '%Y-%m-%d').date() if season_data['air_date'] else None
            season.episode_count = season_data['episode_count']
            
            # Lancer la tâche de mise à jour des épisodes
            update_season_episodes.delay(season.id)
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la série {series_id}: {str(e)}")
        db.session.rollback()
        return False

@shared_task
def update_season_episodes(season_id):
    """Met à jour les épisodes d'une saison depuis TMDB"""
    try:
        season = Season.query.get(season_id)
        if not season:
            return False
            
        series = Series.query.get(season.series_id)
        if not series or not series.tmdb_id:
            return False
            
        response = requests.get(
            f'{TMDB_BASE_URL}/tv/{series.tmdb_id}/season/{season.number}',
            params={
                'api_key': TMDB_API_KEY,
                'language': 'fr-FR'
            }
        )
        
        if response.status_code != 200:
            return False
            
        data = response.json()
        
        for episode_data in data['episodes']:
            episode = Episode.query.filter_by(
                season_id=season.id,
                number=episode_data['episode_number']
            ).first()
            
            if not episode:
                episode = Episode(
                    season_id=season.id,
                    number=episode_data['episode_number']
                )
                db.session.add(episode)
            
            episode.title = episode_data['name']
            episode.description = episode_data['overview']
            episode.air_date = datetime.strptime(episode_data['air_date'], '%Y-%m-%d').date() if episode_data['air_date'] else None
            episode.still = f"https://image.tmdb.org/t/p/w300{episode_data['still_path']}" if episode_data['still_path'] else None
            
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des épisodes de la saison {season_id}: {str(e)}")
        db.session.rollback()
        return False

@shared_task
def generate_recommendations():
    """Génère des recommandations personnalisées pour tous les utilisateurs"""
    from app import User
    from models.content import Progress, Recommendation
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    
    try:
        # Récupérer tous les utilisateurs actifs
        users = User.query.filter(User.last_seen >= datetime.utcnow() - timedelta(days=30)).all()
        
        # Récupérer tous les films et séries
        movies = Movie.query.all()
        series = Series.query.all()
        
        # Créer un vecteur TF-IDF pour le contenu
        content_data = []
        content_ids = []
        
        for movie in movies:
            content = f"{movie.title} {movie.description} {' '.join(g.name for g in movie.genres)}"
            content_data.append(content)
            content_ids.append(('movie', movie.id))
            
        for series in series:
            content = f"{series.title} {series.description} {' '.join(g.name for g in series.genres)}"
            content_data.append(content)
            content_ids.append(('series', series.id))
        
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(content_data)
        
        # Pour chaque utilisateur
        for user in users:
            # Récupérer l'historique de visionnage
            progress = Progress.query.filter_by(user_id=user.id).all()
            
            if not progress:
                continue
            
            # Calculer les scores moyens pour chaque contenu
            user_preferences = np.zeros(len(content_data))
            
            for p in progress:
                if p.progress > 0.5:  # Si l'utilisateur a regardé plus de 50%
                    try:
                        idx = content_ids.index((p.content_type, p.content_id))
                        user_preferences[idx] = p.progress
                    except ValueError:
                        continue
            
            # Calculer les similarités
            if np.sum(user_preferences) > 0:
                similarities = cosine_similarity(
                    tfidf_matrix,
                    tfidf_matrix[user_preferences > 0].mean(axis=0).reshape(1, -1)
                ).flatten()
                
                # Obtenir les meilleurs contenus
                top_indices = similarities.argsort()[-20:][::-1]
                
                # Sauvegarder les recommandations
                Recommendation.query.filter_by(user_id=user.id).delete()
                
                for idx in top_indices:
                    content_type, content_id = content_ids[idx]
                    
                    # Vérifier si l'utilisateur n'a pas déjà vu ce contenu
                    if not Progress.query.filter_by(
                        user_id=user.id,
                        content_type=content_type,
                        content_id=content_id
                    ).first():
                        recommendation = Recommendation(
                            user_id=user.id,
                            content_type=content_type,
                            content_id=content_id,
                            score=float(similarities[idx])
                        )
                        db.session.add(recommendation)
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération des recommandations: {str(e)}")
        db.session.rollback()
        return False

# Configuration des tâches périodiques
@shared_task
def cleanup_old_content():
    """Nettoie le contenu obsolète"""
    try:
        # Supprimer les recommandations de plus d'une semaine
        week_ago = datetime.utcnow() - timedelta(days=7)
        Recommendation.query.filter(Recommendation.created_at < week_ago).delete()
        
        # Supprimer les progressions pour le contenu supprimé
        Progress.query.filter(
            ~Progress.content_id.in_(
                db.session.query(Movie.id).filter(Progress.content_type == 'movie')
            ) & ~Progress.content_id.in_(
                db.session.query(Episode.id).filter(Progress.content_type == 'episode')
            )
        ).delete(synchronize_session=False)
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage du contenu: {str(e)}")
        db.session.rollback()
        return False
