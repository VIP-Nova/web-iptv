from celery import shared_task
import requests
import m3u8
import xmltv
import json
from datetime import datetime, timedelta
from app import db, cache
from models.tv import Channel, Program, Playlist, EPGSource, StreamCache
import re
import concurrent.futures

@shared_task(bind=True, max_retries=3)
def import_m3u_playlist(self, playlist_id):
    """Import channels from M3U playlist"""
    playlist = Playlist.query.get(playlist_id)
    if not playlist:
        return False

    try:
        if playlist.url:
            response = requests.get(playlist.url, timeout=30)
            content = response.text
        else:
            with open(playlist.local_path, 'r', encoding='utf-8') as f:
                content = f.read()

        channels = []
        current_channel = None

        for line in content.splitlines():
            if line.startswith('#EXTINF:'):
                # Parse channel info
                info = parse_extinf(line)
                current_channel = {
                    'name': info.get('name', ''),
                    'logo': info.get('tvg-logo', ''),
                    'group': info.get('group-title', ''),
                    'language': info.get('tvg-language', ''),
                    'country': info.get('tvg-country', ''),
                    'epg_id': info.get('tvg-id', '')
                }
            elif line.startswith('#') or not line.strip():
                continue
            elif current_channel:
                current_channel['stream_url'] = line.strip()
                channels.append(current_channel)
                current_channel = None

        # Bulk update database
        for channel_data in channels:
            channel = Channel.query.filter_by(
                name=channel_data['name'],
                stream_url=channel_data['stream_url']
            ).first()

            if not channel:
                channel = Channel(
                    name=channel_data['name'],
                    stream_url=channel_data['stream_url'],
                    logo=channel_data['logo'],
                    category=channel_data['group'],
                    language=channel_data['language'],
                    country=channel_data['country'],
                    epg_id=channel_data['epg_id']
                )
                db.session.add(channel)

        db.session.commit()
        playlist.last_updated = datetime.utcnow()
        db.session.commit()
        return True

    except Exception as e:
        self.retry(exc=e, countdown=60)

@shared_task(bind=True)
def import_xtream_playlist(self, config):
    """Import channels from Xtream API"""
    try:
        # Login to Xtream API
        login_url = f"http://{config['host']}/player_api.php"
        params = {
            'username': config['username'],
            'password': config['password']
        }
        
        response = requests.get(login_url, params=params)
        data = response.json()
        
        if 'user_info' not in data:
            return False
        
        # Get live streams
        live_streams_url = f"{login_url}&action=get_live_streams"
        response = requests.get(live_streams_url, params=params)
        streams = response.json()
        
        for stream in streams:
            channel = Channel.query.filter_by(
                name=stream['name']
            ).first()
            
            stream_url = f"http://{config['host']}/live/{config['username']}/{config['password']}/{stream['stream_id']}.ts"
            
            if not channel:
                channel = Channel(
                    name=stream['name'],
                    stream_url=stream_url,
                    category=stream.get('category_name', ''),
                    epg_id=stream.get('epg_channel_id', '')
                )
                db.session.add(channel)
            else:
                channel.stream_url = stream_url
                channel.category = stream.get('category_name', '')
                channel.epg_id = stream.get('epg_channel_id', '')
            
        db.session.commit()
        return True
        
    except Exception as e:
        self.retry(exc=e, countdown=60)

@shared_task(bind=True)
def update_epg_data(self, source_id):
    """Update EPG data from XMLTV source"""
    source = EPGSource.query.get(source_id)
    if not source:
        return False

    try:
        if source.url:
            response = requests.get(source.url, timeout=30)
            with open(source.local_path, 'wb') as f:
                f.write(response.content)

        # Parse XMLTV file
        xmltv_parser = xmltv.read_files([source.local_path])
        programs = []

        for program in xmltv_parser:
            channel = Channel.query.filter_by(epg_id=program['channel']).first()
            if not channel:
                continue

            start_time = datetime.strptime(
                program['start'], '%Y%m%d%H%M%S %z'
            ).replace(tzinfo=None)
            
            end_time = datetime.strptime(
                program['stop'], '%Y%m%d%H%M%S %z'
            ).replace(tzinfo=None)

            # Delete existing programs in this time range
            Program.query.filter_by(channel_id=channel.id).filter(
                Program.start_time >= start_time,
                Program.end_time <= end_time
            ).delete()

            # Create new program
            new_program = Program(
                channel_id=channel.id,
                title=program.get('title', [{'value': 'Unknown'}])[0]['value'],
                description=program.get('desc', [{'value': ''}])[0]['value'],
                start_time=start_time,
                end_time=end_time,
                category=program.get('category', [{'value': ''}])[0]['value'],
                rating=program.get('rating', [{'value': ''}])[0]['value']
            )
            programs.append(new_program)

        # Bulk insert new programs
        db.session.bulk_save_objects(programs)
        db.session.commit()

        source.last_updated = datetime.utcnow()
        db.session.commit()
        return True

    except Exception as e:
        self.retry(exc=e, countdown=60)

@shared_task(bind=True)
def check_stream_status(self):
    """Check status of all active streams"""
    channels = Channel.query.filter_by(is_active=True).all()
    
    def check_channel(channel):
        try:
            response = requests.head(channel.stream_url, timeout=5)
            is_working = response.status_code == 200
            
            channel.is_working = is_working
            channel.last_checked = datetime.utcnow()
            
            if not is_working and channel.backup_stream_url:
                channel.stream_url, channel.backup_stream_url = (
                    channel.backup_stream_url,
                    channel.stream_url
                )
            
            return channel
            
        except:
            channel.is_working = False
            channel.last_checked = datetime.utcnow()
            return channel
    
    # Check streams in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        updated_channels = list(executor.map(check_channel, channels))
    
    # Bulk update database
    db.session.bulk_save_objects(updated_channels)
    db.session.commit()

def parse_extinf(line):
    """Parse EXTINF line from M3U file"""
    info = {}
    
    # Get channel name
    name_match = re.search(r',(.+)$', line)
    if name_match:
        info['name'] = name_match.group(1).strip()
    
    # Get attributes
    attrs = re.findall(r'([a-zA-Z0-9-]+)="([^"]*)"', line)
    for key, value in attrs:
        info[key] = value
    
    return info
