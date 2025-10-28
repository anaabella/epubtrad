"""
Plugin para backups automáticos del sistema
"""
import os
import logging
import shutil
import gzip
import json
from datetime import datetime, timedelta
from typing import List
import schedule
import threading
import time

logger = logging.getLogger(__name__)

class BackupPlugin:
    def __init__(self):
        self.name = "backup"
        self.description = "Sistema de backups automáticos"
        self.backup_dir = "backups"
        self.max_backups = 7  # Mantener 7 días de backups

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('system_startup', self.on_system_startup)
        plugin_manager.register_hook('translation_complete', self.on_translation_complete)

    def on_system_startup(self):
        """Hook ejecutado al iniciar el sistema"""
        # Crear directorio de backups
        os.makedirs(self.backup_dir, exist_ok=True)

        # Programar backups automáticos
        self.schedule_backups()

        # Iniciar thread de backups
        backup_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        backup_thread.start()

        logger.info("Sistema de backups inicializado")

    def on_translation_complete(self, user_id: int, titulo: str, capitulos: List, formato: str):
        """Hook ejecutado después de completar una traducción"""
        # Backup después de traducciones importantes
        if len(capitulos) > 10:  # Solo para libros largos
            logger.info(f"Creando backup después de traducción grande: {titulo}")
            self.create_backup("post_translation")

    def schedule_backups(self):
        """Programar backups automáticos"""
        # Backup diario a las 2 AM
        schedule.every().day.at("02:00").do(self.create_daily_backup)

        # Backup semanal los domingos
        schedule.every().sunday.at("03:00").do(self.create_weekly_backup)

        logger.info("Backups automáticos programados")

    def run_scheduler(self):
        """Ejecutar scheduler en loop"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Revisar cada minuto

    def create_daily_backup(self):
        """Crear backup diario"""
        logger.info("Ejecutando backup diario")
        self.create_backup("daily")

    def create_weekly_backup(self):
        """Crear backup semanal"""
        logger.info("Ejecutando backup semanal")
        self.create_backup("weekly")

    def create_backup(self, backup_type: str = "manual"):
        """Crear backup del sistema"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{backup_type}_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)

            os.makedirs(backup_path, exist_ok=True)

            # Archivos a respaldar
            files_to_backup = [
                'storage/user_settings.json',
                'storage/historial.json',
                'storage/authorized_users.txt',
                'storage/banned_users.txt',
                'bot.log',
                'audit.log',
                '.env'
            ]

            # Copiar archivos
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    shutil.copy2(file_path, backup_path)

            # Comprimir backup
            self.compress_backup(backup_path)

            # Limpiar backups antiguos
            self.cleanup_old_backups()

            logger.info(f"Backup creado exitosamente: {backup_name}")

        except Exception as e:
            logger.error(f"Error creando backup: {e}")

    def compress_backup(self, backup_path: str):
        """Comprimir backup usando gzip"""
        try:
            backup_name = os.path.basename(backup_path)
            tar_path = f"{backup_path}.tar.gz"

            # Crear archivo tar.gz
            shutil.make_archive(backup_path, 'gztar', backup_path)

            # Remover directorio original
            shutil.rmtree(backup_path)

            logger.info(f"Backup comprimido: {tar_path}")

        except Exception as e:
            logger.error(f"Error comprimiendo backup: {e}")

    def cleanup_old_backups(self):
        """Eliminar backups antiguos"""
        try:
            backups = []
            for item in os.listdir(self.backup_dir):
                if item.startswith("backup_") and item.endswith(".tar.gz"):
                    path = os.path.join(self.backup_dir, item)
                    mtime = os.path.getmtime(path)
                    backups.append((path, mtime))

            # Ordenar por fecha (más antiguos primero)
            backups.sort(key=lambda x: x[1])

            # Eliminar si hay más del máximo
            while len(backups) > self.max_backups:
                old_backup = backups.pop(0)
                os.remove(old_backup[0])
                logger.info(f"Backup antiguo eliminado: {os.path.basename(old_backup[0])}")

        except Exception as e:
            logger.error(f"Error limpiando backups antiguos: {e}")

    def restore_backup(self, backup_name: str):
        """Restaurar desde backup"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_name)

            if not os.path.exists(backup_path):
                logger.error(f"Backup no encontrado: {backup_name}")
                return False

            # Crear directorio temporal
            temp_dir = f"temp_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(temp_dir)

            # Extraer backup
            shutil.unpack_archive(backup_path, temp_dir, 'gztar')

            # Restaurar archivos
            files_to_restore = [
                'storage/user_settings.json',
                'storage/historial.json',
                'storage/authorized_users.txt',
                'storage/banned_users.txt',
                'bot.log',
                'audit.log',
                '.env'
            ]

            for file_path in files_to_restore:
                temp_file = os.path.join(temp_dir, os.path.basename(file_path))
                if os.path.exists(temp_file):
                    # Crear backup del archivo actual
                    if os.path.exists(file_path):
                        backup_current = f"{file_path}.backup"
                        shutil.copy2(file_path, backup_current)

                    # Restaurar archivo
                    shutil.copy2(temp_file, file_path)

            # Limpiar directorio temporal
            shutil.rmtree(temp_dir)

            logger.info(f"Backup restaurado: {backup_name}")
            return True

        except Exception as e:
            logger.error(f"Error restaurando backup: {e}")
            return False

    def list_backups(self):
        """Listar backups disponibles"""
        try:
            backups = []
            if os.path.exists(self.backup_dir):
                for item in os.listdir(self.backup_dir):
                    if item.startswith("backup_") and item.endswith(".tar.gz"):
                        path = os.path.join(self.backup_dir, item)
                        size = os.path.getsize(path)
                        mtime = os.path.getmtime(path)
                        backups.append({
                            'name': item,
                            'size': size,
                            'date': datetime.fromtimestamp(mtime).isoformat()
                        })

            return sorted(backups, key=lambda x: x['date'], reverse=True)

        except Exception as e:
            logger.error(f"Error listando backups: {e}")
            return []

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'backup': self.manual_backup,
            'list_backups': self.show_backups,
            'restore_backup': self.restore_command
        }

    async def manual_backup(self, update, context):
        """Crear backup manual"""
        await update.message.reply_text("🔄 Creando backup...")
        self.create_backup("manual")
        await update.message.reply_text("✅ Backup creado exitosamente.")

    async def show_backups(self, update, context):
        """Mostrar backups disponibles"""
        backups = self.list_backups()

        if backups:
            msg = "📦 Backups disponibles:\n\n"
            for backup in backups[:10]:  # Mostrar máximo 10
                size_mb = backup['size'] / (1024 * 1024)
                msg += f"📁 {backup['name']}\n"
                msg += f"   📅 {backup['date']}\n"
                msg += f"   📏 {size_mb:.1f} MB\n"
                msg += "\n"
        else:
            msg = "📦 No hay backups disponibles."

        await update.message.reply_text(msg)

    async def restore_command(self, update, context):
        """Comando para restaurar backup"""
        if not context.args:
            await update.message.reply_text("Uso: /restore_backup <nombre_del_backup>")
            return

        backup_name = context.args[0]
        await update.message.reply_text(f"🔄 Restaurando backup: {backup_name}...")

        if self.restore_backup(backup_name):
            await update.message.reply_text("✅ Backup restaurado exitosamente.")
        else:
            await update.message.reply_text("❌ Error restaurando backup.")

# Instancia global
backup_plugin = BackupPlugin()
