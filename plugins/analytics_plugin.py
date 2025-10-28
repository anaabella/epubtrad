"""
Plugin de analytics detallados y reportes
"""
import os
import logging
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Any
import asyncio

logger = logging.getLogger(__name__)

class AnalyticsPlugin:
    def __init__(self):
        self.name = "analytics"
        self.description = "Sistema de analytics detallados y reportes"
        self.analytics_data = defaultdict(dict)
        self.report_scheduler = None

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('system_startup', self.on_system_startup)
        plugin_manager.register_hook('translation_complete', self.on_translation_complete)
        plugin_manager.register_hook('user_request', self.on_user_request)
        plugin_manager.register_hook('error_occurred', self.on_error_occurred)

    def on_system_startup(self):
        """Hook ejecutado al iniciar el sistema"""
        # Cargar datos de analytics existentes
        self.load_analytics_data()

        # Programar generación de reportes
        self.schedule_reports()

        logger.info("Sistema de analytics iniciado")

    def on_translation_complete(self, user_id: int, titulo: str, capitulos: List, formato: str):
        """Hook ejecutado después de completar una traducción"""
        try:
            timestamp = datetime.now()

            # Registrar traducción
            self.analytics_data['translations'].append({
                'user_id': user_id,
                'titulo': titulo,
                'capitulos': len(capitulos),
                'formato': formato,
                'timestamp': timestamp.isoformat(),
                'word_count': sum(len(cap[1].split()) for cap in capitulos)
            })

            # Actualizar estadísticas de usuario
            if str(user_id) not in self.analytics_data['user_stats']:
                self.analytics_data['user_stats'][str(user_id)] = {
                    'total_translations': 0,
                    'total_words': 0,
                    'preferred_format': formato,
                    'last_activity': timestamp.isoformat()
                }

            user_stats = self.analytics_data['user_stats'][str(user_id)]
            user_stats['total_translations'] += 1
            user_stats['total_words'] += sum(len(cap[1].split()) for cap in capitulos)
            user_stats['last_activity'] = timestamp.isoformat()

            # Actualizar formato preferido
            if formato != user_stats.get('preferred_format'):
                # Contar formatos usados por el usuario
                user_formats = [t['formato'] for t in self.analytics_data['translations']
                              if t['user_id'] == user_id]
                if user_formats:
                    user_stats['preferred_format'] = Counter(user_formats).most_common(1)[0][0]

            self.save_analytics_data()

        except Exception as e:
            logger.error(f"Error registrando analytics de traducción: {e}")

    def on_user_request(self, user_id: int, request_type: str):
        """Hook para solicitudes de usuario"""
        try:
            timestamp = datetime.now()
            if 'user_requests' not in self.analytics_data:
                self.analytics_data['user_requests'] = []

            self.analytics_data['user_requests'].append({
                'user_id': user_id,
                'request_type': request_type,
                'timestamp': timestamp.isoformat()
            })

            self.save_analytics_data()

        except Exception as e:
            logger.error(f"Error registrando analytics de request: {e}")

    def on_error_occurred(self, user_id: int, error_type: str, error_msg: str):
        """Hook para errores"""
        try:
            timestamp = datetime.now()
            if 'errors' not in self.analytics_data:
                self.analytics_data['errors'] = []

            self.analytics_data['errors'].append({
                'user_id': user_id,
                'error_type': error_type,
                'error_msg': error_msg,
                'timestamp': timestamp.isoformat()
            })

            self.save_analytics_data()

        except Exception as e:
            logger.error(f"Error registrando analytics de error: {e}")

    def schedule_reports(self):
        """Programar generación automática de reportes"""
        try:
            import schedule
            import time
            import threading

            def generate_daily_report():
                """Generar reporte diario"""
                self.generate_report('daily')

            def generate_weekly_report():
                """Generar reporte semanal"""
                self.generate_report('weekly')

            # Reportes diarios a las 6 AM
            schedule.every().day.at("06:00").do(generate_daily_report)

            # Reportes semanales los lunes
            schedule.every().monday.at("07:00").do(generate_weekly_report)

            # Iniciar scheduler en background
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(60)

            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()

            logger.info("Scheduler de reportes iniciado")

        except Exception as e:
            logger.error(f"Error programando reportes: {e}")

    def generate_report(self, report_type: str):
        """Generar reporte de analytics"""
        try:
            logger.info(f"Generando reporte {report_type}")

            if report_type == 'daily':
                days = 1
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.json"
            elif report_type == 'weekly':
                days = 7
                filename = f"analytics_report_weekly_{datetime.now().strftime('%Y%m%d')}.json"
            else:
                days = 30
                filename = f"analytics_report_monthly_{datetime.now().strftime('%Y%m%d')}.json"

            # Filtrar datos del período
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_translations = [
                t for t in self.analytics_data.get('translations', [])
                if datetime.fromisoformat(t['timestamp']) > cutoff_date
            ]

            # Generar estadísticas
            report = {
                'period': report_type,
                'generated_at': datetime.now().isoformat(),
                'total_translations': len(recent_translations),
                'total_users': len(set(t['user_id'] for t in recent_translations)),
                'total_words': sum(t['word_count'] for t in recent_translations),
                'avg_words_per_translation': 0,
                'popular_formats': {},
                'top_users': [],
                'errors_count': 0
            }

            if recent_translations:
                report['avg_words_per_translation'] = report['total_words'] / len(recent_translations)

                # Formatos populares
                formats = [t['formato'] for t in recent_translations]
                report['popular_formats'] = dict(Counter(formats).most_common())

                # Top usuarios
                user_counts = Counter(t['user_id'] for t in recent_translations)
                report['top_users'] = user_counts.most_common(10)

            # Contar errores
            recent_errors = [
                e for e in self.analytics_data.get('errors', [])
                if datetime.fromisoformat(e['timestamp']) > cutoff_date
            ]
            report['errors_count'] = len(recent_errors)

            # Generar gráficos
            self.generate_charts(recent_translations, report_type)

            # Guardar reporte
            os.makedirs('reports', exist_ok=True)
            report_path = os.path.join('reports', filename)
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Reporte {report_type} generado: {report_path}")

            return report

        except Exception as e:
            logger.error(f"Error generando reporte: {e}")
            return None

    def generate_charts(self, translations: List[Dict], report_type: str):
        """Generar gráficos para el reporte"""
        try:
            if not translations:
                return

            # Preparar datos
            df = pd.DataFrame(translations)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date

            # Gráfico de traducciones por día
            plt.figure(figsize=(12, 6))
            daily_counts = df.groupby('date').size()
            daily_counts.plot(kind='line', marker='o')
            plt.title(f'Traducciones por Día - Reporte {report_type.title()}')
            plt.xlabel('Fecha')
            plt.ylabel('Número de Traducciones')
            plt.xticks(rotation=45)
            plt.tight_layout()

            chart_filename = f"translations_chart_{report_type}_{datetime.now().strftime('%Y%m%d')}.png"
            chart_path = os.path.join('reports', chart_filename)
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()

            # Gráfico de formatos
            plt.figure(figsize=(8, 6))
            format_counts = df['formato'].value_counts()
            format_counts.plot(kind='pie', autopct='%1.1f%%')
            plt.title(f'Distribución de Formatos - Reporte {report_type.title()}')
            plt.ylabel('')

            format_chart_filename = f"formats_chart_{report_type}_{datetime.now().strftime('%Y%m%d')}.png"
            format_chart_path = os.path.join('reports', format_chart_filename)
            plt.savefig(format_chart_path, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"Gráficos generados para reporte {report_type}")

        except Exception as e:
            logger.error(f"Error generando gráficos: {e}")

    def load_analytics_data(self):
        """Cargar datos de analytics"""
        try:
            if os.path.exists('storage/analytics.json'):
                with open('storage/analytics.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convertir defaultdict a dict normal para JSON
                    self.analytics_data.update(data)
                logger.info("Datos de analytics cargados")
        except Exception as e:
            logger.error(f"Error cargando datos de analytics: {e}")

    def save_analytics_data(self):
        """Guardar datos de analytics"""
        try:
            os.makedirs('storage', exist_ok=True)
            with open('storage/analytics.json', 'w', encoding='utf-8') as f:
                json.dump(dict(self.analytics_data), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando datos de analytics: {e}")

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'analytics': self.show_analytics,
            'generate_report': self.generate_report_command
        }

    async def show_analytics(self, update, context):
        """Mostrar estadísticas básicas"""
        try:
            translations = self.analytics_data.get('translations', [])
            total_translations = len(translations)
            total_users = len(self.analytics_data.get('user_stats', {}))

            if translations:
                recent_translations = [
                    t for t in translations
                    if datetime.fromisoformat(t['timestamp']) > datetime.now() - timedelta(days=7)
                ]
                weekly_translations = len(recent_translations)
            else:
                weekly_translations = 0

            msg = f"📊 Analytics del Bot:\n\n"
            msg += f"📖 Traducciones totales: {total_translations}\n"
            msg += f"👥 Usuarios activos: {total_users}\n"
            msg += f"📅 Traducciones esta semana: {weekly_translations}\n"

            await update.message.reply_text(msg)

        except Exception as e:
            logger.error(f"Error mostrando analytics: {e}")
            await update.message.reply_text("❌ Error obteniendo analytics.")

    async def generate_report_command(self, update, context):
        """Generar reporte manual"""
        user_id = update.message.from_user.id
        from main import ADMINS

        if user_id not in ADMINS:
            await update.message.reply_text("❌ No tienes permisos para generar reportes.")
            return

        await update.message.reply_text("🔄 Generando reporte...")

        report = self.generate_report('manual')
        if report:
            await update.message.reply_text("✅ Reporte generado exitosamente.")
        else:
            await update.message.reply_text("❌ Error generando reporte.")

# Instancia global
analytics_plugin = AnalyticsPlugin()
