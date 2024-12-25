from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models.tv import Playlist, EPGSource
from tasks.tv import import_m3u_playlist, import_xtream_playlist, update_epg_data
from app import db

sources = Blueprint('sources', __name__)

@sources.route('/tv/sources')
def manage_sources():
    playlists = Playlist.query.all()
    epg_sources = EPGSource.query.all()
    return render_template('tv/sources.html',
                         playlists=playlists,
                         epg_sources=epg_sources)

@sources.route('/tv/sources/m3u', methods=['POST'])
def add_m3u_source():
    name = request.form.get('name')
    source_type = request.form.get('source_type')
    auto_update = request.form.get('auto_update') == 'on'
    
    playlist = Playlist(
        name=name,
        auto_update=auto_update,
        update_interval=24  # 24 heures par défaut
    )
    
    if source_type == 'url':
        playlist.url = request.form.get('url')
    else:
        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'playlists', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            playlist.local_path = filepath
    
    db.session.add(playlist)
    db.session.commit()
    
    # Lancer la tâche d'import
    import_m3u_playlist.delay(playlist.id)
    
    return jsonify({'status': 'success'})

@sources.route('/tv/sources/xtream', methods=['POST'])
def add_xtream_source():
    data = request.get_json()
    
    playlist = Playlist(
        name=data['name'],
        auto_update=data.get('auto_update', True),
        update_interval=24,  # 24 heures par défaut
        url=f"http://{data['host']}/get.php?username={data['username']}&password={data['password']}&type=m3u_plus"
    )
    
    db.session.add(playlist)
    db.session.commit()
    
    # Lancer la tâche d'import
    import_xtream_playlist.delay({
        'host': data['host'],
        'username': data['username'],
        'password': data['password']
    })
    
    return jsonify({'status': 'success'})

@sources.route('/tv/sources/epg', methods=['POST'])
def add_epg_source():
    name = request.form.get('name')
    source_type = request.form.get('source_type')
    auto_update = request.form.get('auto_update') == 'on'
    
    source = EPGSource(
        name=name,
        auto_update=auto_update,
        update_interval=12  # 12 heures par défaut
    )
    
    if source_type == 'url':
        source.url = request.form.get('url')
    else:
        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'epg', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            source.local_path = filepath
    
    db.session.add(source)
    db.session.commit()
    
    # Lancer la tâche de mise à jour EPG
    update_epg_data.delay(source.id)
    
    return jsonify({'status': 'success'})

@sources.route('/tv/sources/<type>/<int:id>/update', methods=['POST'])
def update_source(type, id):
    if type == 'playlist':
        playlist = Playlist.query.get_or_404(id)
        if playlist.url and playlist.url.startswith('http'):
            import_xtream_playlist.delay({
                'host': playlist.url.split('/')[2],
                'username': playlist.url.split('username=')[1].split('&')[0],
                'password': playlist.url.split('password=')[1].split('&')[0]
            })
        else:
            import_m3u_playlist.delay(id)
    elif type == 'epg':
        update_epg_data.delay(id)
    
    return jsonify({'status': 'success'})

@sources.route('/tv/sources/<type>/<int:id>', methods=['DELETE'])
def delete_source(type, id):
    if type == 'playlist':
        source = Playlist.query.get_or_404(id)
    else:
        source = EPGSource.query.get_or_404(id)
    
    if source.local_path and os.path.exists(source.local_path):
        os.remove(source.local_path)
    
    db.session.delete(source)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@sources.route('/tv/sources/<type>/<int:id>/auto-update', methods=['POST'])
def toggle_auto_update(type, id):
    if type == 'playlist':
        source = Playlist.query.get_or_404(id)
    else:
        source = EPGSource.query.get_or_404(id)
    
    source.auto_update = not source.auto_update
    db.session.commit()
    
    return jsonify({'status': 'success'})
