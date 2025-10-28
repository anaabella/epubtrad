"""
Plugin de integración con redes sociales
"""
import os
import logging
import tweepy
import praw
import discord
from typing import List, Dict, Any, Optional
import asyncio
import json

logger = logging.getLogger(__name__)

class SocialPlugin:
    def __init__(self):
        self.name = "social"
        self.description = "Integración con redes sociales"

        # Configuración de APIs
        self.twitter_api = None
        self.reddit_api = None
        self.discord_bot = None

        # Cargar configuración
        self.load_social_config()

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('translation_complete', self.on_translation_complete)
        plugin_manager.register_hook('system_startup', self.on_system_startup)

    def on_system_startup(self):
        """Hook ejecutado al iniciar el sistema"""
        self.initialize_social_apis()
        logger.info("Plugin social inicializado")

    def on_translation_complete(self, user_id: int, titulo: str, capitulos: List, formato: str):
        """Hook ejecutado después de completar una traducción"""
        try:
            from main import get_user_setting
            if get_user_setting(user_id, 'social_sharing', False):
                asyncio.create_task(self.share_translation(user_id, titulo, formato))
        except Exception as e:
            logger.error(f"Error en social sharing: {e}")

    def load_social_config(self):
        """Cargar configuración de redes sociales"""
        try:
            self.social_config = {}

            # Twitter
            self.social_config['twitter'] = {
                'api_key': os.environ.get('TWITTER_API_KEY'),
                'api_secret': os.environ.get('TWITTER_API_SECRET'),
                'access_token': os.environ.get('TWITTER_ACCESS_TOKEN'),
                'access_token_secret': os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')
            }

            # Reddit
            self.social_config['reddit'] = {
                'client_id': os.environ.get('REDDIT_CLIENT_ID'),
                'client_secret': os.environ.get('REDDIT_CLIENT_SECRET'),
                'user_agent': os.environ.get('REDDIT_USER_AGENT', 'TranslationBot/1.0')
            }

            # Discord
            self.social_config['discord'] = {
                'token': os.environ.get('DISCORD_BOT_TOKEN'),
                'channel_id': os.environ.get('DISCORD_CHANNEL_ID')
            }

        except Exception as e:
            logger.error(f"Error cargando configuración social: {e}")

    def initialize_social_apis(self):
        """Inicializar APIs de redes sociales"""
        try:
            # Twitter
            twitter_config = self.social_config.get('twitter', {})
            if all(twitter_config.values()):
                auth = tweepy.OAuth1UserHandler(
                    twitter_config['api_key'],
                    twitter_config['api_secret'],
                    twitter_config['access_token'],
                    twitter_config['access_token_secret']
                )
                self.twitter_api = tweepy.API(auth)
                logger.info("Twitter API inicializado")

            # Reddit
            reddit_config = self.social_config.get('reddit', {})
            if all(reddit_config.values()):
                self.reddit_api = praw.Reddit(
                    client_id=reddit_config['client_id'],
                    client_secret=reddit_config['client_secret'],
                    user_agent=reddit_config['user_agent']
                )
                logger.info("Reddit API inicializado")

            # Discord
            discord_config = self.social_config.get('discord', {})
            if discord_config.get('token'):
                intents = discord.Intents.default()
                self.discord_bot = discord.Client(intents=intents)
                logger.info("Discord bot inicializado")

        except Exception as e:
            logger.error(f"Error inicializando APIs sociales: {e}")

    async def share_translation(self, user_id: int, titulo: str, formato: str):
        """Compartir traducción en redes sociales"""
        try:
            message = f"📚 ¡Nueva traducción completada! '{titulo}' ahora disponible en {formato.upper()} #Traducción #BotTraductor"

            # Compartir en Twitter
            if self.twitter_api:
                try:
                    self.twitter_api.update_status(message)
                    logger.info(f"Publicado en Twitter: {titulo}")
                except Exception as e:
                    logger.error(f"Error publicando en Twitter: {e}")

            # Compartir en Reddit
            if self.reddit_api:
                try:
                    subreddit = self.reddit_api.subreddit('translations')  # O el subreddit configurado
                    subreddit.submit(title=f"Traducción: {titulo}", selftext=message)
                    logger.info(f"Publicado en Reddit: {titulo}")
                except Exception as e:
                    logger.error(f"Error publicando en Reddit: {e}")

            # Compartir en Discord
            if self.discord_bot and self.social_config['discord'].get('channel_id'):
                try:
                    channel = self.discord_bot.get_channel(int(self.social_config['discord']['channel_id']))
                    if channel:
                        await channel.send(message)
                        logger.info(f"Publicado en Discord: {titulo}")
                except Exception as e:
                    logger.error(f"Error publicando en Discord: {e}")

        except Exception as e:
            logger.error(f"Error compartiendo traducción: {e}")

    def get_social_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de redes sociales"""
        try:
            stats = {
                'twitter_enabled': self.twitter_api is not None,
                'reddit_enabled': self.reddit_api is not None,
                'discord_enabled': self.discord_bot is not None,
                'total_shares': 0  # Implementar contador de shares
            }

            # Aquí se podrían agregar más estadísticas
            return stats

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas sociales: {e}")
            return {}

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'social_toggle': self.toggle_social_sharing,
            'social_stats': self.show_social_stats,
            'share_test': self.test_social_share
        }

    async def toggle_social_sharing(self, update, context):
        """Activar/desactivar compartir en redes sociales"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        current = get_user_setting(user_id, 'social_sharing', False)
        new_value = not current
        set_user_setting(user_id, 'social_sharing', new_value)

        status = "activado" if new_value else "desactivado"
        await update.message.reply_text(f"📱 Compartir en redes sociales {status}.")

    async def show_social_stats(self, update, context):
        """Mostrar estadísticas de redes sociales"""
        stats = self.get_social_stats()

        msg = "📊 Estadísticas de Redes Sociales:\n\n"
        msg += f"🐦 Twitter: {'✅' if stats['twitter_enabled'] else '❌'}\n"
        msg += f"🟠 Reddit: {'✅' if stats['reddit_enabled'] else '❌'}\n"
        msg += f"💙 Discord: {'✅' if stats['discord_enabled'] else '❌'}\n"
        msg += f"📈 Total de shares: {stats['total_shares']}"

        await update.message.reply_text(msg)

    async def test_social_share(self, update, context):
        """Probar compartir en redes sociales"""
        user_id = update.message.from_user.id

        test_title = "Prueba de Traducción"
        test_format = "EPUB"

        await update.message.reply_text("🔄 Probando compartir en redes sociales...")

        await self.share_translation(user_id, test_title, test_format)

        await update.message.reply_text("✅ Prueba de compartir completada. Revisa tus redes sociales.")

# Instancia global
social_plugin = SocialPlugin()
