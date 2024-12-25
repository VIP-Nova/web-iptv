from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import os
from datetime import datetime
import stripe
from werkzeug.utils import secure_filename
from config import config

# Initialisation de l'application
app = Flask(__name__)
app.config.from_object(config['development'])

# Extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
cache = Cache(app)
limiter = Limiter(app, key_func=get_remote_address)
migrate = Migrate(app, db)
admin = Admin(app, name='IPTV Admin', template_mode='bootstrap4')
stripe.api_key = app.config['STRIPE_SECRET_KEY']

# Import des modèles et routes API
from models import *
import api

# Configuration de l'admin
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

admin.add_view(SecureModelView(User, db.session))
admin.add_view(SecureModelView(Playlist, db.session))
admin.add_view(SecureModelView(Channel, db.session))
admin.add_view(SecureModelView(Program, db.session))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes principales
@app.route('/')
def index():
    featured_channels = Channel.query.filter_by(is_active=True).limit(12).all()
    categories = Category.query.filter_by(parent_id=None).all()
    return render_template('index.html', 
                         featured_channels=featured_channels,
                         categories=categories)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            # Enregistrer l'activité
            activity = UserActivity(
                user_id=user.id,
                activity_type='login',
                details={'ip': request.remote_addr}
            )
            db.session.add(activity)
            db.session.commit()
            
            return redirect(url_for('dashboard'))
        flash('Identifiants invalides')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form.get('username')).first():
            flash('Nom d\'utilisateur déjà pris')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email déjà utilisé')
            return redirect(url_for('register'))
            
        user = User(
            username=request.form.get('username'),
            email=request.form.get('email')
        )
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        
        # Envoyer email de bienvenue
        send_welcome_email(user)
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_playlists = current_user.playlists.all()
    favorite_channels = Channel.query.join(Favorite).filter(
        Favorite.user_id == current_user.id
    ).all()
    recent_activity = UserActivity.query.filter_by(
        user_id=current_user.id
    ).order_by(UserActivity.timestamp.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         playlists=user_playlists,
                         favorites=favorite_channels,
                         activity=recent_activity)

@app.route('/browse')
@login_required
def browse():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    language = request.args.get('language')
    quality = request.args.get('quality')
    
    query = Channel.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    if language:
        query = query.filter_by(language=language)
    if quality:
        query = query.filter_by(quality=quality)
        
    channels = query.paginate(page=page, per_page=24)
    
    return render_template('browse.html',
                         channels=channels,
                         category=category,
                         language=language,
                         quality=quality)

@app.route('/watch/<int:channel_id>')
@login_required
def watch(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    
    # Vérifier si l'utilisateur a accès à cette chaîne
    if channel.is_adult and not current_user.is_premium:
        flash('Cette chaîne nécessite un abonnement premium')
        return redirect(url_for('premium'))
        
    # Enregistrer l'activité
    activity = UserActivity(
        user_id=current_user.id,
        activity_type='watch_channel',
        details={'channel_id': channel.id}
    )
    db.session.add(activity)
    db.session.commit()
    
    current_program = Program.query.filter(
        Program.channel_id == channel_id,
        Program.start_time <= datetime.utcnow(),
        Program.end_time >= datetime.utcnow()
    ).first()
    
    next_programs = Program.query.filter(
        Program.channel_id == channel_id,
        Program.start_time >= datetime.utcnow()
    ).limit(5).all()
    
    return render_template('watch.html',
                         channel=channel,
                         current_program=current_program,
                         next_programs=next_programs)

@app.route('/premium')
@login_required
def premium():
    plans = [
        {
            'name': 'Basic',
            'price': 4.99,
            'features': ['Accès à toutes les chaînes', 'HD']
        },
        {
            'name': 'Premium',
            'price': 9.99,
            'features': ['Accès à toutes les chaînes', '4K', 'Contenu adulte', 'Sans publicité']
        },
        {
            'name': 'Family',
            'price': 14.99,
            'features': ['Jusqu\'à 4 écrans', 'Contrôle parental', 'Tout le contenu Premium']
        }
    ]
    return render_template('premium.html', plans=plans)

@app.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    plan = request.form.get('plan')
    
    # Créer la session de paiement Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price': app.config[f'STRIPE_PRICE_ID_{plan.upper()}'],
            'quantity': 1,
        }],
        mode='subscription',
        success_url=url_for('payment_success', _external=True),
        cancel_url=url_for('payment_cancel', _external=True),
        customer_email=current_user.email
    )
    
    return jsonify({'id': session.id})

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_image = filename
                
        current_user.email = request.form.get('email', current_user.email)
        if request.form.get('new_password'):
            current_user.set_password(request.form.get('new_password'))
            
        db.session.commit()
        flash('Profil mis à jour avec succès')
        
    return render_template('profile.html')

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    if not query:
        return render_template('search.html')
        
    channels = Channel.query.filter(
        Channel.name.ilike(f'%{query}%')
    ).limit(20).all()
    
    programs = Program.query.filter(
        Program.title.ilike(f'%{query}%')
    ).limit(20).all()
    
    return render_template('search.html',
                         query=query,
                         channels=channels,
                         programs=programs)

# Utilitaires
def send_welcome_email(user):
    msg = Message(
        'Bienvenue sur IPTV Web',
        recipients=[user.email]
    )
    msg.html = render_template('email/welcome.html', user=user)
    mail.send(msg)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
