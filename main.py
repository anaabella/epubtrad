import os
import re
import requests
import asyncio
import json
import hashlib
from ebooklib import epub
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from langdetect import detect
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import logging
from PyPDF2 import PdfReader
from datetime import datetime, timedelta

# Configurar logging básico antes de intentar importar redis/celery
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import redis
    from celery import Celery
except ImportError:
    logger.warning("Redis/Celery no disponibles, usando alternativas en memoria")
    redis = None
    Celery = None
try:
    import pytesseract
    from PIL import Image
    import cv2
    import deepl
    from dotenv import load_dotenv
except ImportError as e:
    logger.warning(f"Algunos módulos opcionales no disponibles: {e}")
    pytesseract = None
    cv2 = None
    deepl = None
    load_dotenv = lambda: None  # Fallback vacío

# Importar sistema de plugins
from plugins import plugin_manager

# Cargar variables de entorno
load_dotenv()

# Sistema de logs avanzado con rotación
import logging
from logging.handlers import RotatingFileHandler
import os

# Configurar logging con rotación
if not os.path.exists('logs'):
    os.makedirs('logs')

# Handler para archivo con rotación
file_handler = RotatingFileHandler(
    'logs/bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato detallado para archivo
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
file_handler.setFormatter(file_formatter)

# Formato simple para consola
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Configurar logger raíz
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Logs de auditoría
audit_logger = logging.getLogger('audit')
audit_handler = RotatingFileHandler(
    'logs/audit.log',
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3
)
audit_handler.setFormatter(file_formatter)
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

# Configuración de base de datos y caché
if redis:
    REDIS_URL = os.environ.get("REDIS_URL", "").strip()
    if REDIS_URL and REDIS_URL.startswith(('redis://', 'rediss://', 'unix://')):
        try:
            redis_client = redis.from_url(REDIS_URL)
        except Exception as e:
            logger.warning(f"Error conectando a Redis: {e}, usando memoria")
            redis_client = None
    else:
        redis_client = None
else:
    redis_client = None

# Si no hay Redis, usar diccionario en memoria
if redis_client is None:
    class MockRedis:
        def __init__(self):
            self.data = {}
        def get(self, key):
            return self.data.get(key)
        def setex(self, key, time, value):
            self.data[key] = value.encode() if isinstance(value, str) else value
        def incr(self, key):
            self.data[key] = (int(self.data.get(key, 0)) + 1).to_bytes(4, 'big')
    redis_client = MockRedis()

# Configuración de Celery
if Celery:
    celery_app = Celery('tasks', broker=REDIS_URL, backend=REDIS_URL)
else:
    # Fallback sin Celery
    celery_app = None

# Configuración de DeepL
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")

# Historial de últimas 5 traducciones por usuario (persistente)
historial = {}

# Configuraciones de usuario (persistente)
user_settings = {}

# Rate limiting: último uso por usuario
last_usage = {}

# Admins (IDs de Telegram)
ADMINS = [1350300219]  # ID de xuxiilee

# Autenticación de usuarios
AUTHORIZED_USERS = set()  # Whitelist de usuarios autorizados
BANNED_USERS = set()  # Blacklist de usuarios baneados

# Cargar listas de autenticación
def load_auth_lists():
    global AUTHORIZED_USERS, BANNED_USERS
    try:
        if os.path.exists('storage/authorized_users.txt'):
            with open('storage/authorized_users.txt', 'r') as f:
                AUTHORIZED_USERS = set(int(line.strip()) for line in f if line.strip())
        if os.path.exists('storage/banned_users.txt'):
            with open('storage/banned_users.txt', 'r') as f:
                BANNED_USERS = set(int(line.strip()) for line in f if line.strip())
    except Exception as e:
        logger.error(f"Error cargando listas de autenticación: {e}")

# Guardar listas de autenticación
def save_auth_lists():
    try:
        os.makedirs('storage', exist_ok=True)
        with open('storage/authorized_users.txt', 'w') as f:
            for user_id in AUTHORIZED_USERS:
                f.write(f"{user_id}\n")
        with open('storage/banned_users.txt', 'w') as f:
            for user_id in BANNED_USERS:
                f.write(f"{user_id}\n")
    except Exception as e:
        logger.error(f"Error guardando listas de autenticación: {e}")

def check_user_auth(usuario_id):
    """Verifica si un usuario está autorizado"""
    if BANNED_USERS and usuario_id in BANNED_USERS:
        audit_logger.warning(f"Acceso denegado - Usuario baneado: {usuario_id}")
        return False, "Usuario baneado"
    if AUTHORIZED_USERS and usuario_id not in AUTHORIZED_USERS:
        audit_logger.warning(f"Acceso denegado - Usuario no autorizado: {usuario_id}")
        return False, "Usuario no autorizado"
    audit_logger.info(f"Acceso autorizado para usuario: {usuario_id}")
    return True, "Autorizado"

load_auth_lists()

# Cargar datos persistentes al inicio
def load_persistent_data():
    global historial, user_settings
    try:
        if os.path.exists('storage/historial.json'):
            with open('storage/historial.json', 'r') as f:
                historial = json.load(f)
        if os.path.exists('storage/user_settings.json'):
            with open('storage/user_settings.json', 'r') as f:
                user_settings = json.load(f)
    except Exception as e:
        logger.error(f"Error cargando datos persistentes: {e}")

# Guardar datos persistentes
def save_persistent_data():
    try:
        os.makedirs('storage', exist_ok=True)
        with open('storage/historial.json', 'w') as f:
            json.dump(historial, f)
        with open('storage/user_settings.json', 'w') as f:
            json.dump(user_settings, f)
    except Exception as e:
        logger.error(f"Error guardando datos persistentes: {e}")

load_persistent_data()

# ----------------- Gestión de memoria y limpieza de archivos -----------------
try:
    import psutil
    import schedule
    import time
    from datetime import datetime, timedelta
    import glob
except ImportError:
    psutil = None
    schedule = None
    time = __import__('time')
    glob = __import__('glob')
    logger.warning("Módulos de gestión de memoria no disponibles")

def get_memory_usage():
    """Obtener uso de memoria del proceso"""
    if psutil:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    return 0  # Fallback

def cleanup_temp_files():
    """Limpiar archivos temporales antiguos"""
    try:
        # Archivos de más de 1 hora
        cutoff_time = time.time() - 3600

        # Limpiar archivos *_traducido.* en el directorio raíz
        for pattern in ['*_traducido.epub', '*_traducido.pdf']:
            for file_path in glob.glob(pattern):
                if os.path.getmtime(file_path) < cutoff_time:
                    try:
                        os.remove(file_path)
                        logger.info(f"Archivo temporal eliminado: {file_path}")
                    except Exception as e:
                        logger.error(f"Error eliminando {file_path}: {e}")

        # Limpiar archivos descargados temporales
        temp_dir = 'temp'
        if os.path.exists(temp_dir):
            for file_path in glob.glob(os.path.join(temp_dir, '*')):
                if os.path.getmtime(file_path) < cutoff_time:
                    try:
                        os.remove(file_path)
                        logger.info(f"Archivo temp eliminado: {file_path}")
                    except Exception as e:
                        logger.error(f"Error eliminando {file_path}: {e}")

        # Log de memoria
        memory_mb = get_memory_usage()
        logger.info(f"Uso de memoria: {memory_mb:.2f} MB")

        # Alerta si memoria alta
        if memory_mb > 500:  # 500MB
            logger.warning(f"Uso de memoria alto: {memory_mb:.2f} MB")

    except Exception as e:
        logger.error(f"Error en limpieza de archivos: {e}")

# Programar limpieza cada hora
if schedule:
    schedule.every().hour.do(cleanup_temp_files)

def run_scheduled_tasks():
    """Ejecutar tareas programadas en background"""
    if schedule:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Revisar cada minuto
    else:
        logger.warning("Schedule no disponible, tareas programadas deshabilitadas")

# ----------------- Funciones auxiliares -----------------
def get_cache_key(texto, source, target, engine='google'):
    """Generar clave de caché para traducciones"""
    content = f"{texto}|{source}|{target}|{engine}"
    return hashlib.md5(content.encode()).hexdigest()

def traducir_con_cache(texto, source, target, engine='google'):
    """Traducir con caché inteligente"""
    if not texto.strip():
        return ""

    cache_key = get_cache_key(texto, source, target, engine)
    cached_result = redis_client.get(cache_key)
    if cached_result:
        logger.info("Traducción obtenida del caché")
        return cached_result.decode('utf-8')

    result = traducir_texto_engine(texto, source, target, engine)
    if result:
        redis_client.setex(cache_key, 86400, result)  # Cache por 24 horas
    return result

def traducir_texto_engine(texto, source, target, engine='google'):
    """Traducir usando diferentes motores"""
    try:
        if engine == 'deepl' and DEEPL_API_KEY:
            translator = deepl.Translator(DEEPL_API_KEY)
            result = translator.translate_text(texto, source_lang=source.upper(), target_lang=target.upper())
            return str(result)
        else:
            # Fallback a Google
            return traducir_texto_google(texto, source, target)
    except Exception as e:
        logger.error(f"Error con motor {engine}: {str(e)}")
        if engine != 'google':
            return traducir_texto_google(texto, source, target)
        return texto

def traducir_texto_google(texto, source, target):
    """Traducción con Google Translator (original)"""
    try:
        # Dividir el texto en chunks de máximo 3000 caracteres, respetando límites de oraciones
        chunks = []
        current_chunk = ""
        sentences = texto.split('. ')
        for sentence in sentences:
            sentence += '. '  # Restaurar el punto y espacio
            if len(current_chunk + sentence) > 3000:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += sentence
        if current_chunk:
            chunks.append(current_chunk.strip())

        # Asegurar que ningún chunk exceda 5000 caracteres
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > 5000:
                subchunks = [chunk[i:i+2500] for i in range(0, len(chunk), 2500)]
                final_chunks.extend(subchunks)
            else:
                final_chunks.append(chunk)

        traducciones = []
        for chunk in final_chunks:
            try:
                trad = GoogleTranslator(source=source, target=target).translate(chunk)
                traducciones.append(trad)
            except Exception as e:
                logger.error(f"Error traduciendo chunk: {chunk[:50]}... {str(e)}")
                traducciones.append(chunk)  # Mantener original si falla
        return ''.join(traducciones)
    except Exception as e:
        logger.error(f"Error general en traducción: {str(e)}")
        return texto  # Retornar original si falla completamente

# Alias para compatibilidad
def traducir_texto(texto, source, target, usuario_id=None):
    if usuario_id:
        engine = get_user_setting(usuario_id, 'translation_engine', 'google')
        target_lang = get_user_setting(usuario_id, 'target_language', 'es')
    else:
        engine = 'google'
        target_lang = target
    return traducir_con_cache(texto, source, target_lang, engine)

def crear_epub(titulo, capitulos):
    try:
        libro = epub.EpubBook()
        libro.set_identifier(titulo)
        libro.set_title(titulo)
        libro.set_language("es")
        libro.add_author("Bot Traducción")

        items = []
        for idx, (cap_nombre, cap_texto) in enumerate(capitulos):
            c = epub.EpubHtml(title=cap_nombre, file_name=f'chap_{idx}.xhtml', lang='es')
            # Formatear párrafos
            contenido_html = "<h1>{}</h1>".format(cap_nombre)
            for par in cap_texto.split("\n"):
                contenido_html += f"<p>{par}</p>"
            c.set_content(contenido_html)
            libro.add_item(c)
            items.append(c)

        libro.toc = tuple(items)
        libro.spine = ['nav'] + items
        libro.add_item(epub.EpubNcx())
        libro.add_item(epub.EpubNav())

        epub_filename = re.sub(r'[\\/*?:"<>|]', '', titulo) + "_traducido.epub"
        epub.write_epub(epub_filename, libro)
        return epub_filename
    except Exception as e:
        logger.error(f"Error creando EPUB: {str(e)}")
        raise

def crear_pdf(titulo, capitulos):
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for cap_nombre, cap_texto in capitulos:
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, txt=cap_nombre, ln=True, align='L')
            pdf.set_font("Arial", size=12)

            # Dividir el texto en líneas que quepan en la página
            lines = cap_texto.split('\n')
            for line in lines:
                # Codificar en latin-1 para evitar problemas con caracteres especiales
                try:
                    encoded_line = line.encode('latin-1', 'replace').decode('latin-1')
                    pdf.multi_cell(0, 10, txt=encoded_line)
                except:
                    # Si falla la codificación, usar texto básico
                    pdf.multi_cell(0, 10, txt="Texto con caracteres especiales")

        pdf_filename = re.sub(r'[\\/*?:"<>|]', '', titulo) + "_traducido.pdf"
        pdf.output(pdf_filename)
        return pdf_filename
    except Exception as e:
        logger.error(f"Error creando PDF: {str(e)}")
        raise

def crear_archivo_salida(titulo, capitulos, formato):
    if formato.lower() == 'pdf':
        return crear_pdf(titulo, capitulos)
    else:
        return crear_epub(titulo, capitulos)

def agregar_historial(usuario_id, titulo, enlace):
    if usuario_id not in historial:
        historial[usuario_id] = []
    historial[usuario_id].insert(0, (titulo, enlace))
    historial[usuario_id] = historial[usuario_id][:5]  # solo últimas 5 traducciones
    save_persistent_data()  # Guardar cambios persistentes

def get_user_setting(usuario_id, setting, default=True):
    if usuario_id not in user_settings:
        user_settings[usuario_id] = {}
    return user_settings[usuario_id].get(setting, default)

def set_user_setting(usuario_id, setting, value):
    if usuario_id not in user_settings:
        user_settings[usuario_id] = {}
    user_settings[usuario_id][setting] = value
    save_persistent_data()  # Guardar cambios persistentes

def reemplazar_comillas(texto):
    try:
        # Reemplazar diferentes tipos de comillas por guiones dobles (--)
        import re
        # Reemplazar comillas dobles, simples, y sus variantes tipográficas
        texto = re.sub(r'[""''"''"“”‘’]', '―', texto)
        return texto
    except Exception as e:
        logger.error(f"Error reemplazando comillas: {str(e)}")
        return texto

def check_rate_limit(usuario_id):
    now = datetime.now()
    if usuario_id in last_usage:
        time_diff = now - last_usage[usuario_id]
        if time_diff < timedelta(minutes=1):  # 1 solicitud por minuto
            return False
    last_usage[usuario_id] = now
    return True

def detectar_idioma_seguro(texto):
    try:
        return detect(texto)
    except Exception as e:
        logger.warning(f"Error detectando idioma: {str(e)}, asumiendo 'en'")
        return 'en'  # Default a inglés si falla

def procesar_pdf(filename):
    try:
        reader = PdfReader(filename)
        texto = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if not page_text.strip():
                # Si no hay texto extraíble, intentar OCR
                page_text = procesar_pdf_ocr(page)
            texto += page_text + "\n"
        return texto.strip()
    except Exception as e:
        logger.error(f"Error procesando PDF: {str(e)}")
        raise

def procesar_pdf_ocr(page):
    """Extraer texto de página PDF usando OCR"""
    try:
        # Convertir página a imagen
        # Nota: Esto requiere implementación adicional con pdf2image o similar
        # Por simplicidad, devolver vacío por ahora
        return ""
    except Exception as e:
        logger.error(f"Error en OCR: {str(e)}")
        return ""

def procesar_txt(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error procesando TXT: {str(e)}")
        raise

# ----------------- Tareas Celery para procesamiento en background -----------------
if celery_app:
    @celery_app.task
    def traducir_capitulo_task(contenido, idioma_original, usuario_id):
        """Tarea Celery para traducir un capítulo"""
        try:
            contenido_trad = traducir_texto(contenido, idioma_original, "es", usuario_id)
            if get_user_setting(usuario_id, 'reemplazar_comillas'):
                contenido_trad = reemplazar_comillas(contenido_trad)
            return contenido_trad
        except Exception as e:
            logger.error(f"Error en tarea Celery: {str(e)}")
            return contenido
else:
    def traducir_capitulo_task(contenido, idioma_original, usuario_id):
        """Fallback sin Celery - traducción síncrona"""
        try:
            contenido_trad = traducir_texto(contenido, idioma_original, "es", usuario_id)
            if get_user_setting(usuario_id, 'reemplazar_comillas'):
                contenido_trad = reemplazar_comillas(contenido_trad)
            return contenido_trad
        except Exception as e:
            logger.error(f"Error en traducción síncrona: {str(e)}")
            return contenido

# ----------------- Procesar archivos EPUB, PDF, TXT -----------------
async def procesar_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    usuario_id = msg.from_user.id

    # Verificar autenticación
    authorized, reason = check_user_auth(usuario_id)
    if not authorized:
        await msg.reply_text(f"❌ Acceso denegado: {reason}")
        return

    # Rate limiting
    if not check_rate_limit(usuario_id):
        await msg.reply_text("⏳ Has enviado demasiadas solicitudes. Espera 1 minuto antes de enviar otro archivo.")
        return

    logger.info(f"Archivo recibido: {msg.document.file_name} de {msg.from_user.username}")
    try:
        file = await msg.document.get_file()
        filename = msg.document.file_name
        await file.download_to_drive(filename)
        await msg.reply_text(f"Archivo recibido: {filename}\nProcesando...")
        logger.info(f"Archivo descargado: {filename}")
    except Exception as e:
        logger.error(f"Error al descargar archivo: {e}")
        await msg.reply_text("❌ Error al descargar el archivo. Inténtalo de nuevo.")
        return

    if not (filename.lower().endswith((".epub", ".pdf", ".txt"))):
        await msg.reply_text("❌ Solo se soportan archivos EPUB, PDF y TXT")
        return

    # Procesar según tipo de archivo
    try:
        if filename.lower().endswith(".epub"):
            book = epub.read_epub(filename)
            capitulos = []
            items_html = list(book.get_items_of_type(epub.EpubHtml))
            logger.info(f"Procesando EPUB: {filename}, items HTML: {len(items_html)}")

            if not items_html:
                # Intentar con todos los items de tipo 9 (XHTML)
                all_items = list(book.get_items())
                items_html = [item for item in all_items if item.get_type() == 9]
                logger.info(f"Intentando con todos los items de tipo 9 (XHTML): {len(items_html)}")

            for item in items_html:
                contenido_html = item.get_content().decode("utf-8")
                soup = BeautifulSoup(contenido_html, "html.parser")
                # Extraer texto completo del HTML si no hay body, o del body
                texto = soup.get_text(separator='\n').strip()
                if not texto:
                    body = soup.find("body")
                    if body:
                        texto = body.get_text(separator='\n').strip()
                if texto:
                    capitulos.append((item.title or "Capítulo", texto))
                    logger.info(f"Capítulo extraído: {item.title or 'Capítulo'}, longitud: {len(texto)}")

            if not capitulos:
                logger.error("No se pudo extraer contenido del EPUB")
                await msg.reply_text("❌ No se pudo extraer contenido del EPUB")
                return

        elif filename.lower().endswith(".pdf"):
            texto_completo = procesar_pdf(filename)
            capitulos = [("Documento PDF", texto_completo)]
        elif filename.lower().endswith(".txt"):
            texto_completo = procesar_txt(filename)
            capitulos = [("Documento TXT", texto_completo)]
    except Exception as e:
        logger.error(f"Error procesando archivo: {str(e)}")
        await msg.reply_text(f"❌ Error procesando el archivo: {str(e)}")
        return
    logger.info(f"Total capítulos extraídos: {len(capitulos)}")

    idioma_original = detectar_idioma_seguro(capitulos[0][1])
    logger.info(f"Idioma detectado: {idioma_original}")
    progreso_msg = await msg.reply_text("Traduciendo... 0%")

    # Traducir al español usando Celery para archivos grandes
    if idioma_original != "es":
        total = len(capitulos)
        logger.info(f"Iniciando traducción de {total} capítulos")

        if total > 10 and celery_app:  # Para archivos grandes, usar Celery si está disponible
            logger.info("Usando Celery para traducción en background")
            tasks = []
            for nombre, contenido in capitulos:
                task = traducir_capitulo_task.delay(contenido, idioma_original, msg.from_user.id)
                tasks.append((nombre, task))

            for idx, (nombre, task) in enumerate(tasks):
                try:
                    contenido_trad = task.get(timeout=300)  # 5 minutos timeout
                    capitulos[idx] = (nombre, contenido_trad)
                    logger.info(f"Capítulo {idx+1} traducido con Celery")
                except Exception as e:
                    logger.error(f"Error en tarea Celery capítulo {idx+1}: {e}")
                    capitulos[idx] = (nombre, contenido)
                porcentaje = int((idx + 1) / total * 100)
                await progreso_msg.edit_text(f"Traduciendo... {porcentaje}%")
        elif total > 10:  # Fallback sin Celery para archivos grandes
            logger.info("Traduciendo archivo grande sin Celery")
            for idx, (nombre, contenido) in enumerate(capitulos):
                try:
                    contenido_trad = traducir_capitulo_task(contenido, idioma_original, msg.from_user.id)
                    capitulos[idx] = (nombre, contenido_trad)
                    logger.info(f"Capítulo {idx+1} traducido")
                except Exception as e:
                    logger.error(f"Error traduciendo capítulo {idx+1}: {e}")
                    capitulos[idx] = (nombre, contenido)
                porcentaje = int((idx + 1) / total * 100)
                await progreso_msg.edit_text(f"Traduciendo... {porcentaje}%")
        else:
            # Para archivos pequeños, traducción síncrona
            loop = asyncio.get_event_loop()
            for idx, (nombre, contenido) in enumerate(capitulos):
                try:
                    contenido_trad = await loop.run_in_executor(None, traducir_texto, contenido, idioma_original, "es", msg.from_user.id)
                    capitulos[idx] = (nombre, contenido_trad)
                    logger.info(f"Capítulo {idx+1} traducido")
                except Exception as e:
                    logger.error(f"Error traduciendo capítulo {idx+1}: {e}")
                    capitulos[idx] = (nombre, contenido)
                porcentaje = int((idx + 1) / total * 100)
                await progreso_msg.edit_text(f"Traduciendo... {porcentaje}%")
    else:
        # Si ya está en español, aplicar reemplazo de comillas si está activado
        if get_user_setting(msg.from_user.id, 'reemplazar_comillas'):
            for idx, (nombre, contenido) in enumerate(capitulos):
                capitulos[idx] = (nombre, reemplazar_comillas(contenido))

    output_format = get_user_setting(msg.from_user.id, 'output_format', 'epub')
    await progreso_msg.edit_text(f"✅ Traducción completada. Generando {output_format.upper()}...")
    logger.info(f"Generando {output_format.upper()} traducido")
    output_file = crear_archivo_salida(filename, capitulos, output_format)
    logger.info(f"{output_format.upper()} generado: {output_file}")
    await msg.reply_document(document=open(output_file, "rb"), filename=os.path.basename(output_file))
    await progreso_msg.delete()
    logger.info(f"{output_format.upper()} enviado al usuario")

# ----------------- Procesar enlaces (Wattpad, Tumblr, Twitter) -----------------
async def procesar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()
    usuario_id = msg.from_user.id

    # Verificar autenticación
    authorized, reason = check_user_auth(usuario_id)
    if not authorized:
        await msg.reply_text(f"❌ Acceso denegado: {reason}")
        return

    # Rate limiting
    if not check_rate_limit(usuario_id):
        await msg.reply_text("⏳ Has enviado demasiadas solicitudes. Espera 1 minuto antes de enviar otro texto.")
        return

    # Detectar tipo de enlace
    if "wattpad.com/story/" in text or "wattpad.com/user/" in text:
        await procesar_wattpad(msg, text, usuario_id)
    elif "tumblr.com/post/" in text:
        await procesar_tumblr(msg, text, usuario_id)
    else:
        # Procesar como texto normal
        await procesar_texto(msg, text, usuario_id)

async def procesar_wattpad(msg, url, usuario_id):
    await msg.reply_text("📥 Descargando libro de Wattpad...")

    try:
        # Usar WattpadDownloader API (asumiendo que está corriendo en localhost:5042)
        WATTPAD_API_URL = os.environ.get("WATTPAD_API_URL", "http://localhost:5042/api/download")
        response = requests.post(WATTPAD_API_URL, json={"url": url}, timeout=120)
        response.raise_for_status()

        epub_content = response.content
        filename = "wattpad_book.epub"

        # Enviar el EPUB al usuario
        await msg.reply_document(
            document=epub_content,
            filename=filename,
            caption="✅ ¡Libro de Wattpad descargado!"
        )

        # Agregar al historial
        titulo = "Libro de Wattpad"
        agregar_historial(usuario_id, titulo, url)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error descargando de Wattpad: {e}")
        await msg.reply_text("❌ Error al descargar el libro de Wattpad. Verifica que la API esté corriendo o el enlace sea válido.")
    except Exception as e:
        logger.error(f"Error general procesando Wattpad: {e}")
        await msg.reply_text("❌ Error procesando el enlace de Wattpad.")

async def procesar_tumblr(msg, url, usuario_id):
    await msg.reply_text("📥 Convirtiendo post de Tumblr a EPUB...")

    try:
        # Extraer información del URL
        import re
        match = re.search(r'tumblr\.com/post/(\d+)', url)
        if not match:
            await msg.reply_text("❌ Enlace de Tumblr inválido.")
            return

        post_id = match.group(1)
        blog_name = url.split('://')[1].split('.')[0]

        # Usar API de Tumblr si hay credenciales
        TUMBLR_API_KEY = os.environ.get("TUMBLR_API_KEY")
        if TUMBLR_API_KEY:
            # Usar API oficial
            api_url = f"https://api.tumblr.com/v2/blog/{blog_name}.tumblr.com/posts?api_key={TUMBLR_API_KEY}&id={post_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data['response']['posts']:
                post = data['response']['posts'][0]
                titulo = post.get('title', f'Post de {blog_name}')
                contenido = post.get('body', '')

                # Crear EPUB
                capitulos = [(titulo, contenido)]
                epub_file = crear_epub(titulo, capitulos)
                await msg.reply_document(document=open(epub_file, "rb"), filename=os.path.basename(epub_file))
                agregar_historial(usuario_id, titulo, url)
            else:
                await msg.reply_text("❌ Post no encontrado.")
        else:
            # Fallback a scraping básico
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extraer título
            title_tag = soup.find('title')
            titulo = title_tag.text.strip() if title_tag else f'Post de {blog_name}'

            # Extraer contenido (esto puede variar según el tema)
            content_div = soup.select_one('.post-content') or soup.select_one('article') or soup.find('body')
            if content_div:
                # Limpiar el HTML
                for script in content_div(["script", "style"]):
                    script.decompose()
                contenido = content_div.get_text(separator='\n').strip()
            else:
                contenido = "Contenido no encontrado"

            if contenido and len(contenido) > 50:  # Verificar que hay contenido significativo
                capitulos = [(titulo, contenido)]
                epub_file = crear_epub(titulo, capitulos)
                await msg.reply_document(document=open(epub_file, "rb"), filename=os.path.basename(epub_file))
                agregar_historial(usuario_id, titulo, url)
            else:
                await msg.reply_text("❌ No se pudo extraer contenido del post de Tumblr.")

    except Exception as e:
        logger.error(f"Error procesando Tumblr: {e}")
        await msg.reply_text("❌ Error procesando el enlace de Tumblr.")

async def procesar_texto(msg, text, usuario_id):
    await msg.reply_text("🔎 Procesando texto...")

    # ----------------- Procesar texto para traducción -----------------
    titulo = "Texto enviado"
    capitulos = [("Texto", text)]

    capitulos_limpios = []
    for nombre, contenido in capitulos:
        texto = contenido.strip()
        if texto:
            capitulos_limpios.append((nombre, texto))

    if not capitulos_limpios:
        await msg.reply_text("❌ No se pudo procesar el texto")
        return

    idioma_original = detectar_idioma_seguro(capitulos_limpios[0][1])
    progreso_msg = await msg.reply_text("Traduciendo... 0%")

    # Traducir al español de forma asíncrona
    if idioma_original != "es":
        total = len(capitulos_limpios)
        loop = asyncio.get_event_loop()
        for idx, (nombre, contenido) in enumerate(capitulos_limpios):
            try:
                contenido_trad = await loop.run_in_executor(None, traducir_texto, contenido, idioma_original, "es", msg.from_user.id)
                capitulos_limpios[idx] = (nombre, contenido_trad)
            except Exception as e:
                logger.error(f"Error traduciendo capítulo {idx+1}: {e}")
                capitulos_limpios[idx] = (nombre, contenido)
            porcentaje = int((idx + 1) / total * 100)
            await progreso_msg.edit_text(f"Traduciendo... {porcentaje}%")
    else:
        # Si ya está en español, aplicar reemplazo de comillas si está activado
        if get_user_setting(msg.from_user.id, 'reemplazar_comillas'):
            for idx, (nombre, contenido) in enumerate(capitulos_limpios):
                capitulos_limpios[idx] = (nombre, reemplazar_comillas(contenido))

    output_format = get_user_setting(msg.from_user.id, 'output_format', 'epub')
    await progreso_msg.edit_text(f"✅ Traducción completada. Generando {output_format.upper()}...")
    output_file = crear_archivo_salida(titulo, capitulos_limpios, output_format)
    agregar_historial(usuario_id, titulo, text)
    await msg.reply_document(document=open(output_file, "rb"), filename=os.path.basename(output_file))
    await progreso_msg.delete()

# ----------------- Comandos básicos -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id

    # Verificar autenticación
    authorized, reason = check_user_auth(usuario_id)
    if not authorized:
        await update.message.reply_text(f"❌ Acceso denegado: {reason}")
        return

    keyboard = [
        [InlineKeyboardButton("📚 Historial", callback_data='historial')],
        [InlineKeyboardButton("⚙️ Configuraciones", callback_data='settings')],
        [InlineKeyboardButton("👍 Like", callback_data='like'), InlineKeyboardButton("👎 Dislike", callback_data='dislike')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Hola! Envía un EPUB, PDF, TXT o texto para traducirlo.\n\nComandos:\n/settings - Configurar opciones\n/historial - Ver últimas traducciones\n/stats - Estadísticas (solo admins)\n/broadcast - Enviar mensaje a todos (solo admins)",
        reply_markup=reply_markup
    )

async def historial_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id in historial:
        msg = "📚 Últimas traducciones:\n"
        for titulo, enlace in historial[usuario_id]:
            msg += f"- {titulo}\n"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("No tienes historial aún.")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    reemplazar_comillas = get_user_setting(usuario_id, 'reemplazar_comillas')
    target_lang = get_user_setting(usuario_id, 'target_language', 'es')
    translation_engine = get_user_setting(usuario_id, 'translation_engine', 'google')
    output_format = get_user_setting(usuario_id, 'output_format', 'epub').upper()

    keyboard = [
        [InlineKeyboardButton("🔄 Toggle Comillas", callback_data='toggle_comillas')],
        [InlineKeyboardButton(f"🌐 Idioma: {target_lang.upper()}", callback_data='toggle_language')],
        [InlineKeyboardButton(f"🤖 Motor: {translation_engine.title()}", callback_data='toggle_engine')],
        [InlineKeyboardButton(f"📄 Formato: {output_format}", callback_data='toggle_format')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f"⚙️ Configuraciones:\n\nReemplazar comillas: {'Activado' if reemplazar_comillas else 'Desactivado'}\nIdioma destino: {target_lang.upper()}\nMotor de traducción: {translation_engine.title()}\nFormato de salida: {output_format}"
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def toggle_comillas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    current = get_user_setting(usuario_id, 'reemplazar_comillas')
    new_value = not current
    set_user_setting(usuario_id, 'reemplazar_comillas', new_value)
    status = "activado" if new_value else "desactivado"
    await update.message.reply_text(f"✅ Reemplazo de comillas {status}.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id not in ADMINS:
        await update.message.reply_text("❌ No tienes permisos para ver estadísticas.")
        return

    total_users = len(historial)
    total_translations = sum(len(h) for h in historial.values())
    likes = redis_client.get('feedback_likes') or 0
    dislikes = redis_client.get('feedback_dislikes') or 0
    authorized_count = len(AUTHORIZED_USERS) if AUTHORIZED_USERS else "Sin restricción"
    banned_count = len(BANNED_USERS)

    msg = f"📊 Estadísticas del Bot:\n\n👥 Usuarios totales: {total_users}\n📖 Traducciones totales: {total_translations}\n👍 Likes: {int(likes)}\n👎 Dislikes: {int(dislikes)}\n✅ Usuarios autorizados: {authorized_count}\n🚫 Usuarios baneados: {banned_count}"
    await update.message.reply_text(msg)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id not in ADMINS:
        await update.message.reply_text("❌ No tienes permisos para broadcast.")
        return

    # Implementar broadcast a todos los usuarios
    message = " ".join(context.args) if context.args else "Mensaje de broadcast"
    sent_count = 0
    for uid in historial.keys():
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 {message}")
            sent_count += 1
        except Exception as e:
            logger.error(f"Error enviando broadcast a {uid}: {e}")
    await update.message.reply_text(f"✅ Broadcast enviado a {sent_count} usuarios.")

async def authorize_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id not in ADMINS:
        await update.message.reply_text("❌ No tienes permisos para esta acción.")
        return

    try:
        target_user_id = int(context.args[0]) if context.args else None
        if not target_user_id:
            await update.message.reply_text("Uso: /authorize <user_id>")
            return

        AUTHORIZED_USERS.add(target_user_id)
        save_auth_lists()
        audit_logger.info(f"Usuario autorizado por admin {usuario_id}: {target_user_id}")
        await update.message.reply_text(f"✅ Usuario {target_user_id} autorizado.")
    except ValueError:
        await update.message.reply_text("❌ ID de usuario inválido.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id not in ADMINS:
        await update.message.reply_text("❌ No tienes permisos para esta acción.")
        return

    try:
        target_user_id = int(context.args[0]) if context.args else None
        if not target_user_id:
            await update.message.reply_text("Uso: /ban <user_id>")
            return

        BANNED_USERS.add(target_user_id)
        AUTHORIZED_USERS.discard(target_user_id)  # Remover de autorizados si estaba
        save_auth_lists()
        audit_logger.warning(f"Usuario baneado por admin {usuario_id}: {target_user_id}")
        await update.message.reply_text(f"🚫 Usuario {target_user_id} baneado.")
    except ValueError:
        await update.message.reply_text("❌ ID de usuario inválido.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario_id = update.message.from_user.id
    if usuario_id not in ADMINS:
        await update.message.reply_text("❌ No tienes permisos para esta acción.")
        return

    try:
        target_user_id = int(context.args[0]) if context.args else None
        if not target_user_id:
            await update.message.reply_text("Uso: /unban <user_id>")
            return

        BANNED_USERS.discard(target_user_id)
        save_auth_lists()
        audit_logger.info(f"Usuario desbaneado por admin {usuario_id}: {target_user_id}")
        await update.message.reply_text(f"✅ Usuario {target_user_id} desbaneado.")
    except ValueError:
        await update.message.reply_text("❌ ID de usuario inválido.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    usuario_id = query.from_user.id

    if data == 'historial':
        await historial_usuario(update, context)
    elif data == 'settings':
        await settings(update, context)
    elif data == 'toggle_comillas':
        await toggle_comillas(update, context)
    elif data == 'toggle_language':
        current_lang = get_user_setting(usuario_id, 'target_language', 'es')
        new_lang = 'en' if current_lang == 'es' else 'es'
        set_user_setting(usuario_id, 'target_language', new_lang)
        await query.edit_message_text(f"✅ Idioma cambiado a {new_lang.upper()}")
    elif data == 'toggle_engine':
        current_engine = get_user_setting(usuario_id, 'translation_engine', 'google')
        new_engine = 'deepl' if current_engine == 'google' else 'google'
        set_user_setting(usuario_id, 'translation_engine', new_engine)
        await query.edit_message_text(f"✅ Motor de traducción cambiado a {new_engine.title()}")
    elif data == 'toggle_format':
        current_format = get_user_setting(usuario_id, 'output_format', 'epub')
        new_format = 'pdf' if current_format == 'epub' else 'epub'
        set_user_setting(usuario_id, 'output_format', new_format)
        await query.edit_message_text(f"✅ Formato de salida cambiado a {new_format.upper()}")
    elif data == 'like':
        # Sistema de feedback simple
        redis_client.incr('feedback_likes')
        await query.edit_message_text("🙂 ¡Gracias por tu feedback positivo!")
    elif data == 'dislike':
        redis_client.incr('feedback_dislikes')
        await query.edit_message_text("😞 Gracias por tu feedback. Nos esforzaremos por mejorar.")

# ----------------- Inicialización del bot -----------------
def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN no encontrado en variables de entorno")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("historial", historial_usuario))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("toggle_comillas", toggle_comillas))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("authorize", authorize_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(MessageHandler(filters.Document.FileExtension("epub") | filters.Document.FileExtension("pdf") | filters.Document.FileExtension("txt"), procesar_archivo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar))
    app.add_handler(CallbackQueryHandler(button_handler))
    # Remover el handler para enlaces ya que ahora solo procesa texto

    # Cargar plugins
    plugin_manager.load_plugins()
    logger.info("Plugins cargados")

    # Iniciar tareas programadas en background
    import threading
    scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()

    print("Bot iniciado...")
    logger.info("Bot de traducción iniciado correctamente")
    app.run_polling()

if __name__ == "__main__":
    main()