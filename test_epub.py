import os
import re
from ebooklib import epub
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from langdetect import detect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reemplazar_comillas(texto):
    # Reemplazar diferentes tipos de comillas por guiones dobles (--)
    import re
    # Reemplazar comillas dobles, simples, y sus variantes tipográficas
    texto = re.sub(r'[""''"''"“”‘’]', '--', texto)
    return texto

# ----------------- Funciones auxiliares -----------------
def crear_epub(titulo, capitulos):
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

def procesar_epub_local(filename):
    logger.info(f"Procesando EPUB local: {filename}")

    # Leer EPUB
    book = epub.read_epub(filename)
    capitulos = []
    items_list = list(book.get_items_of_type(epub.EpubHtml))
    logger.info(f"Procesando EPUB: {filename}, items HTML: {len(items_list)}")

    # También intentar con otros tipos de items
    all_items = list(book.get_items())
    logger.info(f"Total items en el EPUB: {len(all_items)}")
    for item in all_items:
        logger.info(f"Item: {item.file_name}, type: {item.get_type()}")

    for item in items_list:
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

    # Si no hay items HTML, intentar con todos los items de tipo 9 (que parecen ser XHTML)
    if not capitulos:
        logger.info("Intentando con todos los items de tipo 9 (XHTML)")
        for item in all_items:
            if item.get_type() == 9:  # Tipo XHTML
                try:
                    contenido_html = item.get_content().decode("utf-8")
                    soup = BeautifulSoup(contenido_html, "html.parser")
                    texto = soup.get_text(separator='\n').strip()
                    if not texto:
                        body = soup.find("body")
                        if body:
                            texto = body.get_text(separator='\n').strip()
                    if texto:
                        capitulos.append((item.file_name or "Capítulo", texto))
                        logger.info(f"Capítulo extraído de {item.file_name}: longitud: {len(texto)}")
                except Exception as e:
                    logger.error(f"Error procesando {item.file_name}: {e}")

    if not capitulos:
        logger.error("No se pudo extraer contenido del EPUB")
        return None

    logger.info(f"Total capítulos extraídos: {len(capitulos)}")

    idioma_original = detect(capitulos[0][1])
    logger.info(f"Idioma detectado: {idioma_original}")

    # Traducir al español
    if idioma_original != "es":
        total = len(capitulos)
        logger.info(f"Iniciando traducción de {total} capítulos")
        for idx, (nombre, contenido) in enumerate(capitulos):
            try:
                contenido_trad = GoogleTranslator(source=idioma_original, target="es").translate(contenido)
                capitulos[idx] = (nombre, contenido_trad)
                logger.info(f"Capítulo {idx+1} traducido")
            except Exception as e:
                logger.error(f"Error traduciendo capítulo {idx+1}: {e}")
                capitulos[idx] = (nombre, contenido)
    else:
        # Si ya está en español, aplicar reemplazo de comillas
        for idx, (nombre, contenido) in enumerate(capitulos):
            capitulos[idx] = (nombre, reemplazar_comillas(contenido))

    logger.info("Generando EPUB traducido")
    epub_file = crear_epub(filename, capitulos)
    logger.info(f"EPUB generado: {epub_file}")
    return epub_file

if __name__ == "__main__":
    # Probar con el primer EPUB disponible
    epub_files = [f for f in os.listdir('.') if f.endswith('.epub')]
    if epub_files:
        test_file = epub_files[0]
        logger.info(f"Probando con: {test_file}")
        result = procesar_epub_local(test_file)
        if result:
            logger.info(f"Éxito: {result}")
        else:
            logger.error("Falló el procesamiento")
    else:
        logger.error("No se encontraron archivos EPUB")
