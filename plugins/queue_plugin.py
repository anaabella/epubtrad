"""
Plugin de sistema de colas para traducciones pesadas
"""
import os
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class QueueItem:
    """Elemento de la cola de traducciones"""
    id: str
    user_id: int
    file_path: str
    file_size: int
    priority: int  # 1=low, 2=normal, 3=high, 4=urgent
    status: str  # 'queued', 'processing', 'completed', 'failed'
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
    result_path: Optional[str] = None
    error_msg: Optional[str] = None
    estimated_time: Optional[int] = None  # segundos

class QueuePlugin:
    def __init__(self):
        self.name = "queue"
        self.description = "Sistema de colas para traducciones pesadas"
        self.queue: List[QueueItem] = []
        self.processing_slots = 2  # Máximo de traducciones simultáneas
        self.currently_processing = 0
        self.queue_file = 'storage/translation_queue.json'

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('system_startup', self.on_system_startup)
        plugin_manager.register_hook('large_file_detected', self.on_large_file_detected)
        plugin_manager.register_hook('translation_complete', self.on_translation_complete)

    def on_system_startup(self):
        """Hook ejecutado al iniciar el sistema"""
        self.load_queue()
        asyncio.create_task(self.process_queue())
        logger.info("Sistema de colas iniciado")

    def on_large_file_detected(self, user_id: int, file_path: str, file_size: int):
        """Hook para archivos grandes detectados"""
        # Archivos > 50MB van automáticamente a la cola
        if file_size > 50 * 1024 * 1024:
            self.add_to_queue(user_id, file_path, file_size, priority=3)  # High priority
            return True  # Indicar que se agregó a la cola
        return False

    def on_translation_complete(self, user_id: int, titulo: str, capitulos: List, formato: str):
        """Hook ejecutado después de completar una traducción"""
        # Liberar slot de procesamiento
        self.currently_processing = max(0, self.currently_processing - 1)

    def add_to_queue(self, user_id: int, file_path: str, file_size: int, priority: int = 2) -> str:
        """Agregar elemento a la cola"""
        try:
            item_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()

            # Estimar tiempo basado en tamaño
            estimated_time = self.estimate_processing_time(file_size)

            item = QueueItem(
                id=item_id,
                user_id=user_id,
                file_path=file_path,
                file_size=file_size,
                priority=priority,
                status='queued',
                created_at=created_at,
                estimated_time=estimated_time
            )

            self.queue.append(item)
            self.save_queue()

            # Ordenar cola por prioridad y tiempo de creación
            self.queue.sort(key=lambda x: (-x.priority, x.created_at))

            logger.info(f"Elemento agregado a cola: {item_id} (usuario {user_id})")
            return item_id

        except Exception as e:
            logger.error(f"Error agregando a cola: {e}")
            return None

    def estimate_processing_time(self, file_size: int) -> int:
        """Estimar tiempo de procesamiento en segundos"""
        # Estimación básica: ~1 segundo por 10KB
        base_time = file_size / (10 * 1024)

        # Factor por complejidad (EPUBs son más rápidos que PDFs)
        complexity_factor = 1.5

        # Factor por carga del sistema
        load_factor = 1 + (self.currently_processing / self.processing_slots)

        return int(base_time * complexity_factor * load_factor)

    async def process_queue(self):
        """Procesar elementos de la cola"""
        while True:
            try:
                # Procesar elementos si hay slots disponibles
                while self.currently_processing < self.processing_slots and self.queue:
                    # Encontrar siguiente elemento a procesar
                    pending_items = [item for item in self.queue if item.status == 'queued']

                    if not pending_items:
                        break

                    # Tomar el primero (ya ordenado por prioridad)
                    item = pending_items[0]
                    item.status = 'processing'
                    item.started_at = datetime.now().isoformat()
                    self.currently_processing += 1

                    self.save_queue()

                    # Procesar en background
                    asyncio.create_task(self.process_item(item))

                await asyncio.sleep(5)  # Revisar cada 5 segundos

            except Exception as e:
                logger.error(f"Error procesando cola: {e}")
                await asyncio.sleep(10)

    async def process_item(self, item: QueueItem):
        """Procesar un elemento de la cola"""
        try:
            logger.info(f"Procesando elemento de cola: {item.id}")

            # Simular procesamiento (aquí iría la lógica real de traducción)
            # En una implementación real, llamaríamos a las funciones de traducción

            # Actualizar progreso
            for progress in [0.2, 0.5, 0.8, 1.0]:
                item.progress = progress
                self.save_queue()
                await asyncio.sleep(2)  # Simular tiempo de procesamiento

            # Simular resultado
            item.status = 'completed'
            item.completed_at = datetime.now().isoformat()
            item.result_path = f"processed_{item.file_path}"

            logger.info(f"Elemento procesado exitosamente: {item.id}")

        except Exception as e:
            logger.error(f"Error procesando elemento {item.id}: {e}")
            item.status = 'failed'
            item.error_msg = str(e)

        finally:
            self.save_queue()
            self.currently_processing = max(0, self.currently_processing - 1)

    def get_queue_status(self, user_id: int = None) -> Dict[str, Any]:
        """Obtener estado de la cola"""
        try:
            if user_id:
                user_items = [item for item in self.queue if item.user_id == user_id]
            else:
                user_items = self.queue

            return {
                'total_queued': len([i for i in user_items if i.status == 'queued']),
                'total_processing': len([i for i in user_items if i.status == 'processing']),
                'total_completed': len([i for i in user_items if i.status == 'completed']),
                'total_failed': len([i for i in user_items if i.status == 'failed']),
                'processing_slots': self.processing_slots,
                'currently_processing': self.currently_processing,
                'items': [asdict(item) for item in user_items[-10:]]  # Últimos 10
            }

        except Exception as e:
            logger.error(f"Error obteniendo estado de cola: {e}")
            return {}

    def cancel_item(self, item_id: str, user_id: int) -> bool:
        """Cancelar elemento de la cola"""
        try:
            for item in self.queue:
                if item.id == item_id and item.user_id == user_id:
                    if item.status == 'queued':
                        item.status = 'cancelled'
                        self.save_queue()
                        logger.info(f"Elemento cancelado: {item_id}")
                        return True
                    elif item.status == 'processing':
                        # No se puede cancelar si ya está procesando
                        return False
            return False

        except Exception as e:
            logger.error(f"Error cancelando elemento: {e}")
            return False

    def load_queue(self):
        """Cargar cola desde archivo"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.queue = [QueueItem(**item) for item in data]
                logger.info(f"Cola cargada: {len(self.queue)} elementos")
        except Exception as e:
            logger.error(f"Error cargando cola: {e}")

    def save_queue(self):
        """Guardar cola a archivo"""
        try:
            os.makedirs('storage', exist_ok=True)
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump([asdict(item) for item in self.queue], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando cola: {e}")

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'queue_status': self.show_queue_status,
            'queue_add': self.add_to_queue_command,
            'queue_cancel': self.cancel_queue_item
        }

    async def show_queue_status(self, update, context):
        """Mostrar estado de la cola"""
        user_id = update.message.from_user.id
        status = self.get_queue_status(user_id)

        msg = f"📋 Estado de la Cola de Traducciones:\n\n"
        msg += f"⏳ En cola: {status['total_queued']}\n"
        msg += f"⚙️ Procesando: {status['total_processing']}\n"
        msg += f"✅ Completadas: {status['total_completed']}\n"
        msg += f"❌ Fallidas: {status['total_failed']}\n\n"
        msg += f"🔄 Slots disponibles: {status['processing_slots'] - status['currently_processing']}/{status['processing_slots']}"

        if status['items']:
            msg += "\n\n📝 Tus últimos elementos:\n"
            for item in status['items'][-5:]:  # Últimos 5
                status_emoji = {
                    'queued': '⏳',
                    'processing': '⚙️',
                    'completed': '✅',
                    'failed': '❌'
                }.get(item['status'], '❓')

                msg += f"{status_emoji} {item['id'][:8]}... - {item['status']}\n"

        await update.message.reply_text(msg)

    async def add_to_queue_command(self, update, context):
        """Comando para agregar archivo a la cola manualmente"""
        user_id = update.message.from_user.id

        # Este comando esperaría que el usuario envíe un archivo después
        await update.message.reply_text("📎 Envía el archivo que quieres agregar a la cola de procesamiento.")

        # En una implementación real, guardaríamos el estado del usuario
        # para esperar el archivo siguiente

    async def cancel_queue_item(self, update, context):
        """Cancelar elemento de la cola"""
        user_id = update.message.from_user.id

        if not context.args:
            await update.message.reply_text("Uso: /queue_cancel <id_del_elemento>")
            return

        item_id = context.args[0]

        if self.cancel_item(item_id, user_id):
            await update.message.reply_text(f"✅ Elemento {item_id} cancelado.")
        else:
            await update.message.reply_text(f"❌ No se pudo cancelar el elemento {item_id}.")

# Instancia global
queue_plugin = QueuePlugin()
