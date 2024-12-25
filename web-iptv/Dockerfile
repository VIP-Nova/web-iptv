FROM python:3.11-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    postgresql-client \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Création du répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Création des répertoires nécessaires
RUN mkdir -p /app/uploads/playlists /app/uploads/epg /app/logs

# Configuration de Supervisor
COPY deployment/supervisor.conf /etc/supervisor/conf.d/

# Variables d'environnement
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Exposition des ports
EXPOSE 8000

# Commande de démarrage
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
