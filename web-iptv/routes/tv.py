from flask import Blueprint, render_template, request, jsonify, current_app
from sqlalchemy import or_
from datetime import datetime, timedelta
from models.tv import Channel, Program, ChannelCategory, ViewingStats
from app import db, cache

tv = Blueprint('tv', __name__)

@tv.route('/channels')
@cache.cached(timeout=300)  # Cache for 5 minutes
def channels():
    # Get filters from request
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    quality = request.args.getlist('quality')
    language = request.args.get('language')
    query = request.args.get('q')

    # Base query
    channels_query = Channel.query.filter_by(is_active=True)

    # Apply filters
    if category:
        channels_query = channels_query.join(Channel.categories).filter(
            ChannelCategory.name == category
        )
    
    if quality:
        channels_query = channels_query.filter(Channel.quality.in_(quality))
    
    if language:
        channels_query = channels_query.filter(Channel.language == language)
    
    if query:
        channels_query = channels_query.filter(
            or_(
                Channel.name.ilike(f'%{query}%'),
                Channel.category.ilike(f'%{query}%')
            )
        )

    # Get current programs for each channel
    now = datetime.utcnow()
    channels_with_programs = []
    
    # Paginate results
    channels = channels_query.paginate(
        page=page,
        per_page=current_app.config['CHANNELS_PER_PAGE'],
        error_out=False
    )

    # Get categories for sidebar
    categories = ChannelCategory.query.order_by(ChannelCategory.order).all()
    
    # Get available languages
    languages = db.session.query(Channel.language).distinct().all()
    languages = [lang[0] for lang in languages if lang[0]]

    return render_template('tv/channels.html',
                         channels=channels,
                         categories=categories,
                         languages=languages,
                         current_category=category,
                         selected_quality=quality,
                         selected_language=language,
                         query=query)

@tv.route('/watch/<int:channel_id>')
def watch(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    
    # Get current and upcoming programs
    now = datetime.utcnow()
    programs = Program.query.filter(
        Program.channel_id == channel_id,
        Program.end_time > now
    ).order_by(Program.start_time).limit(10).all()

    # Get current program
    current_program = next(
        (p for p in programs if p.start_time <= now <= p.end_time),
        None
    )

    # Get similar channels
    similar_channels = Channel.query.filter(
        Channel.category == channel.category,
        Channel.id != channel.id,
        Channel.is_active == True
    ).limit(5).all()

    # Update viewing stats
    stats = ViewingStats(
        channel_id=channel_id,
        date=now.date(),
        hour=now.hour
    )
    db.session.add(stats)
    
    # Increment channel views
    channel.views += 1
    db.session.commit()

    return render_template('tv/watch.html',
                         channel=channel,
                         programs=programs,
                         current_program=current_program,
                         similar_channels=similar_channels)

@tv.route('/api/channels/<int:channel_id>/status', methods=['POST'])
def update_channel_status(channel_id):
    """Update channel status (working/not working)"""
    channel = Channel.query.get_or_404(channel_id)
    data = request.get_json()
    
    channel.is_working = data.get('working', True)
    channel.last_checked = datetime.utcnow()
    
    if not channel.is_working and channel.backup_stream_url:
        # Swap to backup URL if main stream is not working
        channel.stream_url, channel.backup_stream_url = (
            channel.backup_stream_url,
            channel.stream_url
        )
    
    db.session.commit()
    return jsonify({'status': 'success'})

@tv.route('/api/channels/<int:channel_id>/quality')
def get_stream_quality(channel_id):
    """Get available stream qualities for a channel"""
    channel = Channel.query.get_or_404(channel_id)
    
    # This would typically be implemented with a streaming server that
    # provides multiple quality options
    qualities = [
        {'name': 'Auto', 'bitrate': 'auto'},
        {'name': '1080p', 'bitrate': '5000k'},
        {'name': '720p', 'bitrate': '2500k'},
        {'name': '480p', 'bitrate': '1000k'},
        {'name': '360p', 'bitrate': '500k'}
    ]
    
    return jsonify(qualities)

@tv.route('/api/epg/now')
def get_current_programs():
    """Get current programs for all channels"""
    now = datetime.utcnow()
    
    current_programs = db.session.query(
        Channel, Program
    ).join(
        Program,
        Channel.id == Program.channel_id
    ).filter(
        Program.start_time <= now,
        Program.end_time > now
    ).all()
    
    return jsonify([{
        'channel_id': channel.id,
        'channel_name': channel.name,
        'program': {
            'title': program.title,
            'start_time': program.start_time.isoformat(),
            'end_time': program.end_time.isoformat(),
            'category': program.category
        }
    } for channel, program in current_programs])

@tv.route('/api/epg/<int:channel_id>')
def get_channel_epg(channel_id):
    """Get EPG data for a specific channel"""
    start_date = request.args.get(
        'start',
        datetime.utcnow().isoformat()
    )
    days = request.args.get('days', 1, type=int)
    
    start_date = datetime.fromisoformat(start_date)
    end_date = start_date + timedelta(days=days)
    
    programs = Program.query.filter(
        Program.channel_id == channel_id,
        Program.start_time >= start_date,
        Program.start_time < end_date
    ).order_by(Program.start_time).all()
    
    return jsonify([{
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'start_time': p.start_time.isoformat(),
        'end_time': p.end_time.isoformat(),
        'category': p.category,
        'rating': p.rating
    } for p in programs])
