"""
Plugin para soporte de múltiples idiomas destino
"""
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MultiLangPlugin:
    def __init__(self):
        self.name = "multi_lang"
        self.description = "Soporte para múltiples idiomas destino"

        # Idiomas soportados con sus códigos
        self.supported_languages = {
            'es': 'Español',
            'en': 'English',
            'fr': 'Français',
            'de': 'Deutsch',
            'it': 'Italiano',
            'pt': 'Português',
            'ru': 'Русский',
            'ja': '日本語',
            'ko': '한국어',
            'zh': '中文',
            'ar': 'العربية',
            'hi': 'हिन्दी'
        }

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('pre_translation', self.on_pre_translation)
        plugin_manager.register_hook('settings_updated', self.on_settings_updated)

    def on_pre_translation(self, user_id: int, text: str, source_lang: str, target_lang: str):
        """Hook ejecutado antes de la traducción"""
        try:
            from main import get_user_setting

            # Verificar si el usuario tiene múltiples idiomas configurados
            multi_langs = get_user_setting(user_id, 'multi_languages', [])
            if multi_langs and len(multi_langs) > 1:
                logger.info(f"Usuario {user_id} tiene múltiples idiomas configurados: {multi_langs}")
                # La traducción se hará a todos los idiomas configurados
                return self.translate_to_multiple(text, source_lang, multi_langs)
            else:
                # Traducción normal a un solo idioma
                return text
        except Exception as e:
            logger.error(f"Error en multi-lang pre-translation: {e}")
        return text

    def on_settings_updated(self, user_id: int, setting: str, value):
        """Hook para cuando se actualizan configuraciones"""
        if setting == 'multi_languages':
            logger.info(f"Idiomas múltiples actualizados para usuario {user_id}: {value}")

    def translate_to_multiple(self, text: str, source_lang: str, target_langs: List[str]):
        """Traducir texto a múltiples idiomas"""
        try:
            translations = {}

            for target_lang in target_langs:
                if target_lang != source_lang:  # No traducir si ya está en el idioma destino
                    translated = self.translate_single(text, source_lang, target_lang)
                    if translated:
                        translations[target_lang] = translated
                    else:
                        translations[target_lang] = text  # Fallback al texto original

            # Combinar todas las traducciones
            combined_text = ""
            for lang_code, translated_text in translations.items():
                lang_name = self.supported_languages.get(lang_code, lang_code.upper())
                combined_text += f"\n\n--- {lang_name} ---\n{translated_text}"

            return combined_text if combined_text else text

        except Exception as e:
            logger.error(f"Error en traducción múltiple: {e}")
            return text

    def translate_single(self, text: str, source_lang: str, target_lang: str) -> str:
        """Traducir a un solo idioma"""
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            return translator.translate(text)
        except Exception as e:
            logger.error(f"Error traduciendo a {target_lang}: {e}")
            return None

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'add_lang': self.add_language,
            'remove_lang': self.remove_language,
            'list_langs': self.list_languages,
            'clear_langs': self.clear_languages
        }

    async def add_language(self, update, context):
        """Agregar idioma a la lista de traducciones múltiples"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        if not context.args:
            # Mostrar lista de idiomas disponibles
            langs_text = "🌐 Idiomas disponibles:\n\n"
            for code, name in self.supported_languages.items():
                langs_text += f"`{code}` - {name}\n"
            langs_text += "\nUso: /add_lang <código_idioma>"
            await update.message.reply_text(langs_text, parse_mode='Markdown')
            return

        lang_code = context.args[0].lower()

        if lang_code not in self.supported_languages:
            await update.message.reply_text(f"❌ Idioma '{lang_code}' no soportado.")
            return

        multi_langs = get_user_setting(user_id, 'multi_languages', [])
        if lang_code not in multi_langs:
            multi_langs.append(lang_code)
            set_user_setting(user_id, 'multi_languages', multi_langs)
            await update.message.reply_text(f"✅ Idioma {self.supported_languages[lang_code]} agregado.")
        else:
            await update.message.reply_text(f"⚠️ El idioma {self.supported_languages[lang_code]} ya está en tu lista.")

    async def remove_language(self, update, context):
        """Remover idioma de la lista de traducciones múltiples"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        if not context.args:
            await update.message.reply_text("Uso: /remove_lang <código_idioma>")
            return

        lang_code = context.args[0].lower()
        multi_langs = get_user_setting(user_id, 'multi_languages', [])

        if lang_code in multi_langs:
            multi_langs.remove(lang_code)
            set_user_setting(user_id, 'multi_languages', multi_langs)
            await update.message.reply_text(f"✅ Idioma {self.supported_languages.get(lang_code, lang_code.upper())} removido.")
        else:
            await update.message.reply_text(f"⚠️ El idioma {lang_code} no está en tu lista.")

    async def list_languages(self, update, context):
        """Listar idiomas configurados para traducciones múltiples"""
        user_id = update.message.from_user.id
        from main import get_user_setting

        multi_langs = get_user_setting(user_id, 'multi_languages', [])

        if multi_langs:
            msg = "🌐 Idiomas configurados para traducción múltiple:\n\n"
            for lang_code in multi_langs:
                lang_name = self.supported_languages.get(lang_code, lang_code.upper())
                msg += f"• {lang_name} ({lang_code})\n"
            msg += f"\nTotal: {len(multi_langs)} idiomas"
        else:
            msg = "🌐 No tienes idiomas configurados para traducción múltiple.\n\nUsa /add_lang <código> para agregar idiomas."

        await update.message.reply_text(msg)

    async def clear_languages(self, update, context):
        """Limpiar todos los idiomas de traducción múltiple"""
        user_id = update.message.from_user.id
        from main import set_user_setting

        set_user_setting(user_id, 'multi_languages', [])
        await update.message.reply_text("✅ Todos los idiomas de traducción múltiple han sido removidos.")

# Instancia global
multi_lang_plugin = MultiLangPlugin()
