from celery import Celery
from celery.schedules import crontab
import requests
import m3u8
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from app import app, db
from models import Channel, Program, Playlist, UserActivity
import logging

celery = Celery('tasks', broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

logger = logging.getLogger(__name__)

@celery.task
def update_playlist(playlist_id):
    """Met à jour les chaînes d'une playlist à partir de son URL M3U"""
    try:
        playlist = Playlist.query.get(playlist_id)
        if not playlist:
            return False
            
        response = requests.get(playlist.url)
        if response.status_code != 200:
            return False
            
        m3u_content = response.text
        playlist_obj = m3u8.loads(m3u_content)
        
        # Supprimer les anciennes chaînes
        Channel.query.filter_by(playlist_id=playlist_id).delete()
        
        # Ajouter les nouvelles chaînes
        for stream in playlist_obj.segments:
            if stream.uri and stream.title:
                channel = Channel(
                    name=stream.title,
                    url=stream.uri,
                    playlist_id=playlist_id
                )
                db.session.add(channel)
        
        playlist.last_updated = datetime.utcnow()
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la playlist {playlist_id}: {str(e)}")
        return False

@celery.task
def update_epg():
    """Met à jour le guide des programmes (EPG) pour toutes les chaînes"""
    try:
        # Récupérer les sources EPG configurées
        epg_sources = [
            "http://example.com/epg.xml",  # À remplacer par vos vraies sources EPG
        ]
        
        for source in epg_sources:
            response = requests.get(source)
            if response.status_code != 200:
                continue
                
            root = ET.fromstring(response.content)
            
            for program in root.findall(".//programme"):
                channel_id = program.get('channel')
                channel = Channel.query.filter_by(epg_id=channel_id).first()
                
                if channel:
                    start_time = datetime.strptime(program.get('start'), '%Y%m%d%H%M%S %z')
                    end_time = datetime.strptime(program.get('stop'), '%Y%m%d%H%M%S %z')
                    
                    title = program.find('title').text
                    desc = program.find('desc')
                    description = desc.text if desc is not None else ''
                    
                    new_program = Program(
                        channel_id=channel.id,
                        title=title,
                        description=description,
                        start_time=start_time,
                        end_time=end_time
                    )
                    db.session.add(new_program)
            
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour EPG: {str(e)}")
        return False

@celery.task
def check_channel_status():
    """Vérifie le statut des chaînes et marque celles qui ne sont plus disponibles"""
    try:
        channels = Channel.query.all()
        for channel in channels:
            try:
                response = requests.head(channel.url, timeout=5)
                channel.is_active = response.status_code == 200
            except:
                channel.is_active = False
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des chaînes: {str(e)}")
        return False

@celery.task
def clean_old_programs():
    """Supprime les anciens programmes du guide TV"""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        Program.query.filter(Program.end_time < week_ago).delete()
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des programmes: {str(e)}")
        return False

@celery.task
def send_notifications():
    """Envoie des notifications aux utilisateurs pour leurs programmes en watchlist"""
    from app import mail
    from flask_mail import Message
    
    try:
        # Trouver les programmes qui commencent dans 15 minutes
        start_time = datetime.utcnow() + timedelta(minutes=15)
        programs = Program.query.filter(
            Program.start_time <= start_time,
            Program.start_time > datetime.utcnow()
        ).all()
        
        for program in programs:
            # Trouver les utilisateurs qui ont ce programme dans leur watchlist
            watchlist_items = WatchlistItem.query.filter_by(
                program_id=program.id,
                notify=True
            ).all()
            
            for item in watchlist_items:
                msg = Message(
                    f"Votre programme commence bientôt : {program.title}",
                    recipients=[item.user.email]
                )
                msg.body = f"""
                Bonjour {item.user.username},
                
                Le programme {program.title} va commencer dans 15 minutes sur {program.channel.name}.
                
                Ne le manquez pas !
                """
                mail.send(msg)
                
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi des notifications: {str(e)}")
        return False

# Configuration des tâches périodiques
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Mise à jour EPG toutes les 12 heures
    sender.add_periodic_task(
        crontab(hour='*/12'),
        update_epg.s()
    )
    
    # Vérification des chaînes toutes les heures
    sender.add_periodic_task(
        crontab(minute=0),
        check_channel_status.s()
    )
    
    # Nettoyage des vieux programmes tous les jours à minuit
    sender.add_periodic_task(
        crontab(hour=0, minute=0),
        clean_old_programs.s()
    )
    
    # Envoi des notifications toutes les 5 minutes
    sender.add_periodic_task(
        300.0,
        send_notifications.s()
    )
