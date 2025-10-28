"""
Interfaz web de administración para el bot
"""
try:
    from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
    from flask_cors import CORS
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    from io import BytesIO
    import base64
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask no disponible, web admin deshabilitado")

import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def create_app():
    if not FLASK_AVAILABLE:
        return None
    app = Flask(__name__)
    CORS(app)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')

    # Configurar rutas
    @app.route('/')
    def dashboard():
        """Dashboard principal"""
        try:
            # Cargar estadísticas
            stats = get_bot_stats()

            # Generar gráficos
            charts = generate_charts()

            return render_template('dashboard.html',
                                 stats=stats,
                                 charts=charts,
                                 active_page='dashboard')
        except Exception as e:
            logger.error(f"Error en dashboard: {e}")
            return render_template('error.html', error=str(e))

    @app.route('/users')
    def users():
        """Gestión de usuarios"""
        try:
            user_data = get_user_data()
            return render_template('users.html',
                                 users=user_data,
                                 active_page='users')
        except Exception as e:
            logger.error(f"Error en users: {e}")
            return render_template('error.html', error=str(e))

    @app.route('/logs')
    def logs():
        """Visualización de logs"""
        try:
            log_entries = get_recent_logs()
            return render_template('logs.html',
                                 logs=log_entries,
                                 active_page='logs')
        except Exception as e:
            logger.error(f"Error en logs: {e}")
            return render_template('error.html', error=str(e))

    @app.route('/settings')
    def settings():
        """Configuración del bot"""
        try:
            bot_settings = get_bot_settings()
            return render_template('settings.html',
                                 settings=bot_settings,
                                 active_page='settings')
        except Exception as e:
            logger.error(f"Error en settings: {e}")
            return render_template('error.html', error=str(e))

    @app.route('/api/stats')
    def api_stats():
        """API para estadísticas"""
        try:
            stats = get_bot_stats()
            return jsonify(stats)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/users/<int:user_id>/ban', methods=['POST'])
    def ban_user(user_id):
        """API para banear usuario"""
        try:
            from main import set_user_setting
            set_user_setting(user_id, 'banned', True)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/users/<int:user_id>/unban', methods=['POST'])
    def unban_user(user_id):
        """API para desbanear usuario"""
        try:
            from main import set_user_setting
            set_user_setting(user_id, 'banned', False)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app

def get_bot_stats():
    """Obtener estadísticas del bot"""
    try:
        stats = {
            'total_users': 0,
            'total_translations': 0,
            'active_users_today': 0,
            'total_files_processed': 0,
            'memory_usage': 0,
            'uptime': 'N/A'
        }

        # Cargar datos de usuarios
        if os.path.exists('storage/user_settings.json'):
            with open('storage/user_settings.json', 'r') as f:
                user_settings = json.load(f)
                stats['total_users'] = len(user_settings)

        # Cargar historial
        if os.path.exists('storage/historial.json'):
            with open('storage/historial.json', 'r') as f:
                historial = json.load(f)
                stats['total_translations'] = sum(len(books) for books in historial.values())

        # Calcular usuarios activos hoy
        today = datetime.now().date()
        active_users = set()
        for user_id, books in historial.items():
            for _, timestamp in books:
                if isinstance(timestamp, str):
                    book_date = datetime.fromisoformat(timestamp).date()
                else:
                    book_date = datetime.fromtimestamp(timestamp).date()
                if book_date == today:
                    active_users.add(user_id)
        stats['active_users_today'] = len(active_users)

        # Contar archivos procesados
        epub_files = len([f for f in os.listdir('.') if f.endswith('_traducido.epub')])
        stats['total_files_processed'] = epub_files

        return stats

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return {}

def get_user_data():
    """Obtener datos de usuarios"""
    try:
        users = []
        if os.path.exists('storage/user_settings.json'):
            with open('storage/user_settings.json', 'r') as f:
                user_settings = json.load(f)

            for user_id, settings in user_settings.items():
                user_info = {
                    'id': user_id,
                    'settings': settings,
                    'last_active': 'N/A',
                    'total_translations': 0
                }

                # Obtener historial del usuario
                if os.path.exists('storage/historial.json'):
                    with open('storage/historial.json', 'r') as f:
                        historial = json.load(f)
                        if str(user_id) in historial:
                            user_books = historial[str(user_id)]
                            user_info['total_translations'] = len(user_books)
                            if user_books:
                                # Última traducción
                                last_book = user_books[-1]
                                if isinstance(last_book[1], str):
                                    user_info['last_active'] = last_book[1]
                                else:
                                    user_info['last_active'] = datetime.fromtimestamp(last_book[1]).isoformat()

                users.append(user_info)

        return users

    except Exception as e:
        logger.error(f"Error obteniendo datos de usuarios: {e}")
        return []

def get_recent_logs():
    """Obtener logs recientes"""
    try:
        logs = []
        if os.path.exists('bot.log'):
            with open('bot.log', 'r') as f:
                lines = f.readlines()[-100:]  # Últimas 100 líneas
                for line in lines:
                    # Parsear línea de log
                    try:
                        parts = line.strip().split(' - ', 3)
                        if len(parts) >= 4:
                            timestamp = parts[0]
                            level = parts[1]
                            module = parts[2]
                            message = parts[3]
                            logs.append({
                                'timestamp': timestamp,
                                'level': level,
                                'module': module,
                                'message': message
                            })
                    except:
                        logs.append({
                            'timestamp': 'N/A',
                            'level': 'UNKNOWN',
                            'module': 'N/A',
                            'message': line.strip()
                        })
        return logs[::-1]  # Más recientes primero

    except Exception as e:
        logger.error(f"Error obteniendo logs: {e}")
        return []

def get_bot_settings():
    """Obtener configuración del bot"""
    try:
        settings = {}
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        # Ocultar valores sensibles
                        if 'key' in key.lower() or 'token' in key.lower():
                            value = '*' * len(value)
                        settings[key] = value
        return settings

    except Exception as e:
        logger.error(f"Error obteniendo configuración: {e}")
        return {}

def generate_charts():
    """Generar gráficos para el dashboard"""
    try:
        charts = {}

        # Gráfico de traducciones por día
        if os.path.exists('storage/historial.json'):
            with open('storage/historial.json', 'r') as f:
                historial = json.load(f)

            # Recopilar datos
            dates = []
            for user_books in historial.values():
                for _, timestamp in user_books:
                    if isinstance(timestamp, str):
                        date = datetime.fromisoformat(timestamp).date()
                    else:
                        date = datetime.fromtimestamp(timestamp).date()
                    dates.append(date)

            if dates:
                df = pd.DataFrame({'date': dates})
                df['count'] = 1
                daily_counts = df.groupby('date').count()

                plt.figure(figsize=(10, 6))
                plt.plot(daily_counts.index, daily_counts['count'])
                plt.title('Traducciones por Día')
                plt.xlabel('Fecha')
                plt.ylabel('Número de Traducciones')
                plt.xticks(rotation=45)

                # Convertir a base64
                buffer = BytesIO()
                plt.savefig(buffer, format='png', bbox_inches='tight')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                charts['translations_chart'] = f'data:image/png;base64,{image_base64}'
                plt.close()

        return charts

    except Exception as e:
        logger.error(f"Error generando gráficos: {e}")
        return {}

# Crear aplicación Flask
app = create_app()

if __name__ == '__main__':
    if app:
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Web admin no disponible debido a dependencias faltantes")
