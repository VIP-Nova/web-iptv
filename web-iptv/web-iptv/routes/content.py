from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db, cache
from models.content import (
    Movie, Series, Season, Episode, Genre, Actor, Director,
    Creator, Review, Watchlist, Progress, Collection, CollectionItem
)
from datetime import datetime, timedelta

content = Blueprint('content', __name__)

# Routes pour les films
@content.route('/movies')
@login_required
def movies():
    page = request.args.get('page', 1, type=int)
    genre = request.args.get('genre')
    sort = request.args.get('sort', 'latest')
    search = request.args.get('q')
    
    query = Movie.query
    
    if genre:
        query = query.filter(Movie.genres.any(name=genre))
    
    if search:
        query = query.filter(
            or_(
                Movie.title.ilike(f'%{search}%'),
                Movie.original_title.ilike(f'%{search}%')
            )
        )
    
    if sort == 'latest':
        query = query.order_by(Movie.release_date.desc())
    elif sort == 'rating':
        query = query.order_by(Movie.rating.desc())
    elif sort == 'views':
        query = query.order_by(Movie.views.desc())
    
    movies = query.paginate(page=page, per_page=24)
    genres = Genre.query.all()
    
    return render_template('content/movies.html',
                         movies=movies,
                         genres=genres,
                         current_genre=genre,
                         current_sort=sort)

@content.route('/movie/<int:movie_id>')
@login_required
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # Incrémenter le compteur de vues
    movie.views += 1
    db.session.commit()
    
    # Récupérer la progression de l'utilisateur
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        content_type='movie',
        content_id=movie_id
    ).first()
    
    # Récupérer les films similaires
    similar_movies = Movie.query.filter(
        Movie.genres.any(Genre.id.in_([g.id for g in movie.genres]))
    ).filter(Movie.id != movie_id).limit(6).all()
    
    # Récupérer les avis
    reviews = Review.query.filter_by(
        content_type='movie',
        content_id=movie_id
    ).order_by(Review.created_at.desc()).limit(10).all()
    
    return render_template('content/movie_detail.html',
                         movie=movie,
                         progress=progress,
                         similar_movies=similar_movies,
                         reviews=reviews)

@content.route('/movie/<int:movie_id>/watch')
@login_required
def watch_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # Vérifier si l'utilisateur a accès au contenu premium
    if movie.quality in ['FHD', '4K'] and not current_user.is_premium:
        flash('Ce contenu nécessite un abonnement premium')
        return redirect(url_for('premium'))
    
    # Récupérer ou créer la progression
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        content_type='movie',
        content_id=movie_id
    ).first()
    
    if not progress:
        progress = Progress(
            user_id=current_user.id,
            content_type='movie',
            content_id=movie_id,
            progress=0
        )
        db.session.add(progress)
        db.session.commit()
    
    return render_template('content/watch_movie.html',
                         movie=movie,
                         progress=progress)

# Routes pour les séries
@content.route('/series')
@login_required
def series_list():
    page = request.args.get('page', 1, type=int)
    genre = request.args.get('genre')
    status = request.args.get('status')
    sort = request.args.get('sort', 'latest')
    search = request.args.get('q')
    
    query = Series.query
    
    if genre:
        query = query.filter(Series.genres.any(name=genre))
    
    if status:
        query = query.filter_by(status=status)
    
    if search:
        query = query.filter(
            or_(
                Series.title.ilike(f'%{search}%'),
                Series.original_title.ilike(f'%{search}%')
            )
        )
    
    if sort == 'latest':
        query = query.order_by(Series.start_date.desc())
    elif sort == 'rating':
        query = query.order_by(Series.rating.desc())
    elif sort == 'views':
        query = query.order_by(Series.total_views.desc())
    
    series_list = query.paginate(page=page, per_page=24)
    genres = Genre.query.all()
    
    return render_template('content/series_list.html',
                         series_list=series_list,
                         genres=genres,
                         current_genre=genre,
                         current_status=status,
                         current_sort=sort)

@content.route('/series/<int:series_id>')
@login_required
def series_detail(series_id):
    series = Series.query.get_or_404(series_id)
    
    # Incrémenter le compteur de vues
    series.total_views += 1
    db.session.commit()
    
    # Récupérer la dernière saison regardée
    last_progress = Progress.query.join(Episode).join(Season).filter(
        Progress.user_id == current_user.id,
        Season.series_id == series_id
    ).order_by(Progress.last_watched.desc()).first()
    
    # Récupérer les séries similaires
    similar_series = Series.query.filter(
        Series.genres.any(Genre.id.in_([g.id for g in series.genres]))
    ).filter(Series.id != series_id).limit(6).all()
    
    # Récupérer les avis
    reviews = Review.query.filter_by(
        content_type='series',
        content_id=series_id
    ).order_by(Review.created_at.desc()).limit(10).all()
    
    return render_template('content/series_detail.html',
                         series=series,
                         last_progress=last_progress,
                         similar_series=similar_series,
                         reviews=reviews)

@content.route('/series/<int:series_id>/season/<int:season_number>')
@login_required
def season_detail(series_id, season_number):
    series = Series.query.get_or_404(series_id)
    season = Season.query.filter_by(
        series_id=series_id,
        number=season_number
    ).first_or_404()
    
    # Récupérer la progression pour chaque épisode
    episode_progress = {
        p.content_id: p for p in Progress.query.filter(
            Progress.user_id == current_user.id,
            Progress.content_type == 'episode',
            Progress.content_id.in_([e.id for e in season.episodes])
        ).all()
    }
    
    return render_template('content/season_detail.html',
                         series=series,
                         season=season,
                         episode_progress=episode_progress)

@content.route('/watch/episode/<int:episode_id>')
@login_required
def watch_episode(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    season = episode.season
    series = season.series
    
    # Vérifier si l'utilisateur a accès au contenu premium
    if episode.quality in ['FHD', '4K'] and not current_user.is_premium:
        flash('Ce contenu nécessite un abonnement premium')
        return redirect(url_for('premium'))
    
    # Récupérer ou créer la progression
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        content_type='episode',
        content_id=episode_id
    ).first()
    
    if not progress:
        progress = Progress(
            user_id=current_user.id,
            content_type='episode',
            content_id=episode_id,
            progress=0
        )
        db.session.add(progress)
        db.session.commit()
    
    # Récupérer l'épisode suivant
    next_episode = Episode.query.filter(
        Episode.season_id == season.id,
        Episode.number > episode.number
    ).first()
    
    if not next_episode:
        next_season = Season.query.filter(
            Season.series_id == series.id,
            Season.number > season.number
        ).first()
        if next_season:
            next_episode = Episode.query.filter_by(
                season_id=next_season.id,
                number=1
            ).first()
    
    return render_template('content/watch_episode.html',
                         episode=episode,
                         progress=progress,
                         next_episode=next_episode)

# Routes pour les collections
@content.route('/collections')
@login_required
def collections():
    # Collections de l'utilisateur
    user_collections = Collection.query.filter_by(user_id=current_user.id).all()
    
    # Collections publiques populaires
    popular_collections = Collection.query.filter_by(
        is_public=True
    ).order_by(
        Collection.id.desc()
    ).limit(10).all()
    
    return render_template('content/collections.html',
                         user_collections=user_collections,
                         popular_collections=popular_collections)

@content.route('/collection/<int:collection_id>')
@login_required
def collection_detail(collection_id):
    collection = Collection.query.get_or_404(collection_id)
    
    # Vérifier les permissions
    if not collection.is_public and collection.user_id != current_user.id:
        flash('Vous n\'avez pas accès à cette collection')
        return redirect(url_for('content.collections'))
    
    items = CollectionItem.query.filter_by(
        collection_id=collection_id
    ).order_by(CollectionItem.order).all()
    
    # Récupérer les détails des items
    content_items = []
    for item in items:
        if item.content_type == 'movie':
            content = Movie.query.get(item.content_id)
        else:
            content = Series.query.get(item.content_id)
        if content:
            content_items.append((item, content))
    
    return render_template('content/collection_detail.html',
                         collection=collection,
                         items=content_items)

# API Routes pour les interactions AJAX
@content.route('/api/progress', methods=['POST'])
@login_required
def update_progress():
    data = request.get_json()
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        content_type=data['content_type'],
        content_id=data['content_id']
    ).first()
    
    if progress:
        progress.progress = data['progress']
        progress.last_watched = datetime.utcnow()
    else:
        progress = Progress(
            user_id=current_user.id,
            content_type=data['content_type'],
            content_id=data['content_id'],
            progress=data['progress']
        )
        db.session.add(progress)
    
    db.session.commit()
    return jsonify({'status': 'success'})

@content.route('/api/watchlist/<content_type>/<int:content_id>', methods=['POST', 'DELETE'])
@login_required
def toggle_watchlist(content_type, content_id):
    if request.method == 'POST':
        if not Watchlist.query.filter_by(
            user_id=current_user.id,
            content_type=content_type,
            content_id=content_id
        ).first():
            watchlist = Watchlist(
                user_id=current_user.id,
                content_type=content_type,
                content_id=content_id
            )
            db.session.add(watchlist)
            db.session.commit()
        return jsonify({'status': 'added'})
    else:
        Watchlist.query.filter_by(
            user_id=current_user.id,
            content_type=content_type,
            content_id=content_id
        ).delete()
        db.session.commit()
        return jsonify({'status': 'removed'})

@content.route('/api/review', methods=['POST'])
@login_required
def add_review():
    data = request.get_json()
    
    review = Review(
        user_id=current_user.id,
        content_type=data['content_type'],
        content_id=data['content_id'],
        rating=data['rating'],
        comment=data['comment']
    )
    
    db.session.add(review)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'review': {
            'user': current_user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%d/%m/%Y %H:%M')
        }
    })
