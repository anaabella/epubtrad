"""
Plugin de integración con servicios cloud (Google Drive, Dropbox, etc.)
"""
import os
import logging
import dropbox
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class CloudPlugin:
    def __init__(self):
        self.name = "cloud"
        self.description = "Integración con servicios cloud"

        # Servicios disponibles
        self.dropbox_client = None
        self.google_drive_service = None

        # Configuración
        self.load_cloud_config()

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('system_startup', self.on_system_startup)
        plugin_manager.register_hook('translation_complete', self.on_translation_complete)

    def on_system_startup(self):
        """Hook ejecutado al iniciar el sistema"""
        self.initialize_cloud_services()
        logger.info("Plugin cloud inicializado")

    def on_translation_complete(self, user_id: int, titulo: str, capitulos: List, formato: str):
        """Hook ejecutado después de completar una traducción"""
        try:
            from main import get_user_setting
            cloud_service = get_user_setting(user_id, 'cloud_service', None)
            if cloud_service:
                # Subir archivo traducido automáticamente
                output_file = f"{titulo.replace(' ', '_')}_traducido.{formato.lower()}"
                if os.path.exists(output_file):
                    asyncio.create_task(self.upload_to_cloud(user_id, output_file, cloud_service))
        except Exception as e:
            logger.error(f"Error en cloud upload: {e}")

    def load_cloud_config(self):
        """Cargar configuración de servicios cloud"""
        try:
            self.cloud_config = {}

            # Dropbox
            self.cloud_config['dropbox'] = {
                'access_token': os.environ.get('DROPBOX_ACCESS_TOKEN')
            }

            # Google Drive
            self.cloud_config['google_drive'] = {
                'credentials_path': os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials.json'),
                'token_path': os.environ.get('GOOGLE_TOKEN_PATH', 'token.json')
            }

        except Exception as e:
            logger.error(f"Error cargando configuración cloud: {e}")

    def initialize_cloud_services(self):
        """Inicializar servicios cloud"""
        try:
            # Dropbox
            dropbox_config = self.cloud_config.get('dropbox', {})
            if dropbox_config.get('access_token'):
                self.dropbox_client = dropbox.Dropbox(dropbox_config['access_token'])
                logger.info("Dropbox inicializado")

            # Google Drive
            drive_config = self.cloud_config.get('google_drive', {})
            if os.path.exists(drive_config.get('token_path', 'token.json')):
                creds = Credentials.from_authorized_user_file(drive_config['token_path'])
                self.google_drive_service = build('drive', 'v3', credentials=creds)
                logger.info("Google Drive inicializado")

        except Exception as e:
            logger.error(f"Error inicializando servicios cloud: {e}")

    async def upload_to_cloud(self, user_id: int, file_path: str, service: str):
        """Subir archivo a servicio cloud"""
        try:
            if service == 'dropbox' and self.dropbox_client:
                await self.upload_to_dropbox(user_id, file_path)
            elif service == 'google_drive' and self.google_drive_service:
                await self.upload_to_google_drive(user_id, file_path)
            else:
                logger.warning(f"Servicio cloud no disponible: {service}")

        except Exception as e:
            logger.error(f"Error subiendo a {service}: {e}")

    async def upload_to_dropbox(self, user_id: int, file_path: str):
        """Subir archivo a Dropbox"""
        try:
            file_name = os.path.basename(file_path)
            dropbox_path = f"/Traducciones/{user_id}/{file_name}"

            with open(file_path, 'rb') as f:
                self.dropbox_client.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

            logger.info(f"Archivo subido a Dropbox: {dropbox_path}")

        except Exception as e:
            logger.error(f"Error subiendo a Dropbox: {e}")

    async def upload_to_google_drive(self, user_id: int, file_path: str):
        """Subir archivo a Google Drive"""
        try:
            file_name = os.path.basename(file_path)

            # Crear carpeta si no existe
            folder_id = await self.get_or_create_folder(user_id)

            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }

            media = MediaFileUpload(file_path, resumable=True)
            file = self.google_drive_service.files().create(
                body=file_metadata, media_body=media, fields='id'
            ).execute()

            logger.info(f"Archivo subido a Google Drive: {file.get('id')}")

        except Exception as e:
            logger.error(f"Error subiendo a Google Drive: {e}")

    def get_or_create_folder(self, user_id: int) -> str:
        """Obtener o crear carpeta en Google Drive"""
        try:
            # Buscar carpeta existente
            query = f"name='Traducciones_{user_id}' and mimeType='application/vnd.google-apps.folder'"
            results = self.google_drive_service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get('files', [])

            if items:
                return items[0]['id']

            # Crear nueva carpeta
            folder_metadata = {
                'name': f'Traducciones_{user_id}',
                'mimeType': 'application/vnd.google-apps.folder'
            }

            folder = self.google_drive_service.files().create(
                body=folder_metadata, fields='id'
            ).execute()

            return folder.get('id')

        except Exception as e:
            logger.error(f"Error creando carpeta en Drive: {e}")
            return None

    def list_cloud_files(self, user_id: int, service: str) -> List[Dict[str, Any]]:
        """Listar archivos en la nube"""
        try:
            files = []

            if service == 'dropbox' and self.dropbox_client:
                path = f"/Traducciones/{user_id}"
                result = self.dropbox_client.files_list_folder(path)
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        files.append({
                            'name': entry.name,
                            'size': entry.size,
                            'modified': entry.server_modified.isoformat()
                        })

            elif service == 'google_drive' and self.google_drive_service:
                folder_id = self.get_or_create_folder(user_id)
                if folder_id:
                    query = f"'{folder_id}' in parents"
                    results = self.google_drive_service.files().list(q=query, fields="files(id, name, size, modifiedTime)").execute()
                    for item in results.get('files', []):
                        files.append({
                            'name': item['name'],
                            'size': int(item.get('size', 0)),
                            'modified': item.get('modifiedTime', '')
                        })

            return files

        except Exception as e:
            logger.error(f"Error listando archivos en {service}: {e}")
            return []

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'cloud_setup': self.setup_cloud_service,
            'cloud_upload': self.upload_command,
            'cloud_list': self.list_cloud_files_command,
            'cloud_toggle': self.toggle_auto_upload
        }

    async def setup_cloud_service(self, update, context):
        """Configurar servicio cloud"""
        user_id = update.message.from_user.id

        if not context.args:
            msg = "☁️ Servicios cloud disponibles:\n\n"
            msg += "• dropbox - Dropbox\n"
            msg += "• google_drive - Google Drive\n\n"
            msg += "Uso: /cloud_setup <servicio>"
            await update.message.reply_text(msg)
            return

        service = context.args[0].lower()
        available_services = ['dropbox', 'google_drive']

        if service not in available_services:
            await update.message.reply_text(f"❌ Servicio '{service}' no disponible.")
            return

        from main import set_user_setting
        set_user_setting(user_id, 'cloud_service', service)
        await update.message.reply_text(f"✅ Servicio cloud configurado: {service.title()}")

    async def upload_command(self, update, context):
        """Subir archivo actual a la nube"""
        user_id = update.message.from_user.id
        from main import get_user_setting

        service = get_user_setting(user_id, 'cloud_service', None)
        if not service:
            await update.message.reply_text("❌ Primero configura un servicio cloud con /cloud_setup")
            return

        # Este comando esperaría que el usuario envíe un archivo
        await update.message.reply_text(f"📎 Envía el archivo para subir a {service.title()}.")

    async def list_cloud_files_command(self, update, context):
        """Listar archivos en la nube"""
        user_id = update.message.from_user.id
        from main import get_user_setting

        service = get_user_setting(user_id, 'cloud_service', None)
        if not service:
            await update.message.reply_text("❌ No tienes un servicio cloud configurado.")
            return

        await update.message.reply_text(f"🔄 Obteniendo archivos de {service.title()}...")

        files = self.list_cloud_files(user_id, service)

        if files:
            msg = f"☁️ Archivos en {service.title()}:\n\n"
            for file in files[:10]:  # Máximo 10
                size_mb = file['size'] / (1024 * 1024)
                msg += f"📄 {file['name']}\n"
                msg += f"   📏 {size_mb:.1f} MB\n"
                msg += f"   📅 {file['modified'][:10]}\n\n"
        else:
            msg = f"☁️ No hay archivos en {service.title()}."

        await update.message.reply_text(msg)

    async def toggle_auto_upload(self, update, context):
        """Activar/desactivar subida automática a la nube"""
        user_id = update.message.from_user.id
        from main import get_user_setting, set_user_setting

        current = get_user_setting(user_id, 'auto_cloud_upload', False)
        new_value = not current
        set_user_setting(user_id, 'auto_cloud_upload', new_value)

        status = "activada" if new_value else "desactivada"
        await update.message.reply_text(f"☁️ Subida automática a la nube {status}.")

# Instancia global
cloud_plugin = CloudPlugin()
