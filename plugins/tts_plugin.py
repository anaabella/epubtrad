"""
Plugin de Text-to-Speech para convertir traducciones a audio
"""
import os
import logging
from gtts import gTTS
from typing import List, Tuple

logger = logging.getLogger(__name__)

class TtsPlugin:
    def __init__(self):
        self.name = "tts"
        self.description = "Convierte traducciones a audio usando Google TTS"

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('post_translation', self.on_post_translation)
        plugin_manager.register_hook('settings_updated', self.on_settings_updated)

    def on_post_translation(self, user_id: int, titulo: str, capitulos: List[Tuple[str, str]], formato: str):
        """Hook ejecutado después de una traducción completa"""
        try:
            # Verificar si el usuario tiene TTS activado
            from main import get_user_setting
            if not get_user_setting(user_id, 'tts_enabled', False):
                return

            logger.info(f"Generando audio TTS para {titulo} (usuario {user_id})")

            # Combinar todo el texto
            full_text = ""
            for cap_nombre, cap_texto in capitulos:
                full_text += f"{cap_nombre}\n\n{cap_texto}\n\n"

            # Generar audio
            tts = gTTS(text=full_text[:5000], lang='es', slow=False)  # Limitar a 5000 chars

            # Guardar archivo
            audio_filename = f"{titulo.replace(' ', '_')}_tts.mp3"
            audio_path = os.path.join('temp', audio_filename)
            os.makedirs('temp', exist_ok=True)
            tts.save(audio_path)

            logger.info(f"Audio TTS generado: {audio_path}")

            # Aquí se podría enviar el audio al usuario
            # await context.bot.send_audio(chat_id=user_id, audio=open(audio_path, 'rb'))

        except Exception as e:
            logger.error(f"Error en TTS plugin: {e}")

    def on_settings_updated(self, user_id: int, setting: str, value):
        """Hook para cuando se actualizan configuraciones"""
        if setting == 'tts_enabled':
            status = "activado" if value else "desactivado"
            logger.info(f"TTS {status} para usuario {user_id}")

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'tts_toggle': self.toggle_tts
        }

    async def toggle_tts(self, update, context):
        """Comando para activar/desactivar TTS"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        current = get_user_setting(user_id, 'tts_enabled', False)
        new_value = not current
        set_user_setting(user_id, 'tts_enabled', new_value)

        status = "activado" if new_value else "desactivado"
        await update.message.reply_text(f"🔊 TTS {status}.")
