"""
Plugin para optimización de memoria con procesamiento streaming
"""
import os
import logging
import asyncio
from typing import List, Tuple, Iterator
import gc

logger = logging.getLogger(__name__)

class StreamingPlugin:
    def __init__(self):
        self.name = "streaming"
        self.description = "Optimización de memoria para archivos grandes usando streaming"

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('pre_translation', self.on_pre_translation)
        plugin_manager.register_hook('process_large_file', self.on_process_large_file)

    def on_pre_translation(self, user_id: int, text: str, source_lang: str, target_lang: str):
        """Hook ejecutado antes de la traducción"""
        # Verificar si el texto es muy grande
        if len(text) > 100000:  # Más de 100KB
            logger.info(f"Texto grande detectado para usuario {user_id}, activando modo streaming")
            return self.process_large_text_streaming(text, source_lang, target_lang)
        return text

    def on_process_large_file(self, user_id: int, file_path: str, file_size: int):
        """Hook para procesar archivos grandes"""
        if file_size > 10 * 1024 * 1024:  # Más de 10MB
            logger.info(f"Archivo grande detectado: {file_path} ({file_size} bytes)")
            return self.process_large_file_streaming(file_path)
        return None

    def process_large_text_streaming(self, text: str, source_lang: str, target_lang: str) -> str:
        """Procesar texto grande usando streaming para ahorrar memoria"""
        try:
            # Dividir en chunks más pequeños para traducción
            chunk_size = 5000  # Caracteres por chunk
            chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

            translated_chunks = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Procesando chunk {i+1}/{len(chunks)}")
                translated_chunk = self.translate_chunk(chunk, source_lang, target_lang)
                translated_chunks.append(translated_chunk)

                # Liberar memoria
                gc.collect()

            return ''.join(translated_chunks)

        except Exception as e:
            logger.error(f"Error en procesamiento streaming: {e}")
            # Fallback a traducción normal
            from main import traducir_texto
            return traducir_texto(text, source_lang, target_lang)

    def translate_chunk(self, chunk: str, source_lang: str, target_lang: str) -> str:
        """Traducir un chunk individual"""
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            return translator.translate(chunk)
        except Exception as e:
            logger.error(f"Error traduciendo chunk: {e}")
            return chunk  # Retornar original si falla

    def process_large_file_streaming(self, file_path: str):
        """Procesar archivo grande usando streaming"""
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Procesando archivo grande en streaming: {file_path}")

            # Para EPUBs grandes, procesar capítulo por capítulo
            if file_path.endswith('.epub'):
                return self.process_epub_streaming(file_path)

            # Para otros archivos, implementar lógica específica
            return None

        except Exception as e:
            logger.error(f"Error procesando archivo grande: {e}")
            return None

    def process_epub_streaming(self, epub_path: str):
        """Procesar EPUB grande capítulo por capítulo"""
        try:
            from ebooklib import epub
            import tempfile

            book = epub.read_epub(epub_path)

            # Crear libro de salida
            output_book = epub.EpubBook()
            output_book.set_identifier(book.get_metadata('DC', 'identifier')[0][0] + '_translated')
            output_book.set_title(book.get_metadata('DC', 'title')[0][0] + ' (Translated)')
            output_book.set_language('es')

            items = []
            spine = ['nav']

            # Procesar cada elemento
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    logger.info(f"Procesando capítulo: {item.get_name()}")

                    # Extraer texto
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    text_content = soup.get_text()

                    # Traducir si hay texto significativo
                    if len(text_content.strip()) > 100:
                        translated_text = self.process_large_text_streaming(text_content, 'auto', 'es')

                        # Reconstruir HTML con texto traducido
                        # Esto es simplificado - en producción necesitarías preservar estructura HTML
                        new_content = f"<html><body><h1>{item.get_name()}</h1><p>{translated_text.replace(chr(10), '</p><p>')}</p></body></html>"

                        item.set_content(new_content.encode('utf-8'))

                    items.append(item)
                    spine.append(item.get_name())

                else:
                    # Copiar elementos no textuales (imágenes, CSS, etc.)
                    items.append(item)

            # Agregar items al libro
            for item in items:
                output_book.add_item(item)

            # Crear tabla de contenidos
            output_book.toc = tuple(items)
            output_book.add_item(epub.EpubNcx())
            output_book.add_item(epub.EpubNav())
            output_book.spine = spine

            # Guardar
            output_filename = os.path.basename(epub_path).replace('.epub', '_streaming_traducido.epub')
            epub.write_epub(output_filename, output_book)

            logger.info(f"EPUB procesado en streaming: {output_filename}")
            return output_filename

        except Exception as e:
            logger.error(f"Error procesando EPUB en streaming: {e}")
            return None

    def get_memory_usage(self) -> float:
        """Obtener uso de memoria actual"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_percent()
        except ImportError:
            return 0.0

    def cleanup_memory(self):
        """Liberar memoria"""
        gc.collect()
        logger.info("Memoria limpiada")

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'memory': self.show_memory_usage,
            'cleanup': self.force_cleanup
        }

    async def show_memory_usage(self, update, context):
        """Mostrar uso de memoria"""
        usage = self.get_memory_usage()
        await update.message.reply_text(f"🧠 Uso de memoria: {usage:.1f}%")

    async def force_cleanup(self, update, context):
        """Forzar limpieza de memoria"""
        self.cleanup_memory()
        await update.message.reply_text("🧹 Memoria limpiada.")

# Instancia global
streaming_plugin = StreamingPlugin()
