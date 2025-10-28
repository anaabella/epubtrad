"""
Plugin de IA Generativa para mejorar traducciones y generar contenido
"""
import os
import logging
import openai
import anthropic
from typing import List, Tuple

logger = logging.getLogger(__name__)

class AiPlugin:
    def __init__(self):
        self.name = "ai"
        self.description = "Usa IA generativa para mejorar traducciones y generar resúmenes"

        # Configurar APIs
        self.openai_client = None
        self.anthropic_client = None

        openai_key = os.environ.get("OPENAI_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if openai_key:
            self.openai_client = openai.OpenAI(api_key=openai_key)
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('pre_translation', self.on_pre_translation)
        plugin_manager.register_hook('post_translation', self.on_post_translation)

    def on_pre_translation(self, user_id: int, text: str, source_lang: str, target_lang: str):
        """Hook ejecutado antes de la traducción"""
        try:
            from main import get_user_setting
            if get_user_setting(user_id, 'ai_improve_translation', False):
                logger.info(f"Mejorando traducción con IA para usuario {user_id}")
                improved_text = self.improve_translation(text, source_lang, target_lang)
                return improved_text if improved_text else text
        except Exception as e:
            logger.error(f"Error en AI pre-translation: {e}")
        return text

    def on_post_translation(self, user_id: int, titulo: str, capitulos: List[Tuple[str, str]], formato: str):
        """Hook ejecutado después de la traducción"""
        try:
            from main import get_user_setting
            if get_user_setting(user_id, 'ai_generate_summary', False):
                logger.info(f"Generando resumen con IA para {titulo}")
                summary = self.generate_summary(capitulos)
                if summary:
                    # Agregar capítulo de resumen
                    capitulos.append(("Resumen IA", summary))
        except Exception as e:
            logger.error(f"Error en AI post-translation: {e}")

    def improve_translation(self, text: str, source_lang: str, target_lang: str) -> str:
        """Mejorar traducción usando IA"""
        if not self.openai_client and not self.anthropic_client:
            return None

        prompt = f"""Mejora esta traducción del {source_lang} al {target_lang}, manteniendo el significado original pero haciendo el texto más natural y fluido:

Texto original: {text[:2000]}

Proporciona solo la traducción mejorada:"""

        try:
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error llamando a IA: {e}")
            return None

    def generate_summary(self, capitulos: List[Tuple[str, str]]) -> str:
        """Generar resumen del libro usando IA"""
        if not self.openai_client and not self.anthropic_client:
            return None

        # Combinar texto de los primeros capítulos para el resumen
        full_text = ""
        for cap_nombre, cap_texto in capitulos[:3]:  # Solo primeros 3 capítulos
            full_text += f"{cap_nombre}: {cap_texto[:500]}\n"

        prompt = f"""Genera un resumen conciso de este libro basado en los siguientes capítulos:

{full_text[:2000]}

Resumen:"""

        try:
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.5
                )
                return response.choices[0].message.content.strip()
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    temperature=0.5,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error generando resumen con IA: {e}")
            return None

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'ai_improve': self.toggle_ai_improve,
            'ai_summary': self.toggle_ai_summary
        }

    async def toggle_ai_improve(self, update, context):
        """Activar/desactivar mejora de traducciones con IA"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        current = get_user_setting(user_id, 'ai_improve_translation', False)
        new_value = not current
        set_user_setting(user_id, 'ai_improve_translation', new_value)

        status = "activado" if new_value else "desactivado"
        await update.message.reply_text(f"🤖 Mejora de traducciones con IA {status}.")

    async def toggle_ai_summary(self, update, context):
        """Activar/desactivar generación de resúmenes con IA"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        current = get_user_setting(user_id, 'ai_generate_summary', False)
        new_value = not current
        set_user_setting(user_id, 'ai_generate_summary', new_value)

        status = "activado" if new_value else "desactivado"
        await update.message.reply_text(f"📝 Generación de resúmenes con IA {status}.")
