"""
Plugin completo de OCR para PDFs usando Tesseract y OpenCV
"""
import os
import logging
import cv2
import pytesseract
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
from typing import List, Tuple

logger = logging.getLogger(__name__)

class OcrPlugin:
    def __init__(self):
        self.name = "ocr"
        self.description = "OCR completo para PDFs con preprocesamiento de imágenes"

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('process_pdf_ocr', self.on_process_pdf_ocr)
        plugin_manager.register_hook('pre_translation', self.on_pre_translation)

    def on_process_pdf_ocr(self, pdf_path: str) -> str:
        """Hook para procesar PDF con OCR completo"""
        try:
            logger.info(f"Iniciando OCR completo para: {pdf_path}")
            text = self.extract_text_with_ocr(pdf_path)
            logger.info(f"OCR completado, texto extraído: {len(text)} caracteres")
            return text
        except Exception as e:
            logger.error(f"Error en OCR plugin: {e}")
            return ""

    def on_pre_translation(self, user_id: int, text: str, source_lang: str, target_lang: str):
        """Hook para preprocesar texto antes de traducción"""
        # Aquí podríamos aplicar OCR si el texto parece ser imagen
        pass

    def extract_text_with_ocr(self, pdf_path: str) -> str:
        """Extraer texto de PDF usando OCR con preprocesamiento"""
        try:
            # Convertir PDF a imágenes
            images = convert_from_path(pdf_path, dpi=300)

            extracted_text = []
            for i, image in enumerate(images):
                logger.info(f"Procesando página {i+1}/{len(images)}")

                # Convertir PIL a OpenCV
                opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

                # Preprocesamiento de imagen
                processed_image = self.preprocess_image(opencv_image)

                # Extraer texto con Tesseract
                text = pytesseract.image_to_string(processed_image, lang='eng+spa')

                if text.strip():
                    extracted_text.append(f"--- Página {i+1} ---\n{text.strip()}")

            return "\n\n".join(extracted_text)

        except Exception as e:
            logger.error(f"Error en extracción OCR: {e}")
            return ""

    def preprocess_image(self, image):
        """Preprocesar imagen para mejorar OCR"""
        try:
            # Convertir a escala de grises
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Aplicar filtro de desenfoque para reducir ruido
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Aplicar threshold adaptativo
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # Operaciones morfológicas para limpiar
            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)

            # Redimensionar si es necesario
            height, width = processed.shape
            if height < 300:
                scale_factor = 300 / height
                new_width = int(width * scale_factor)
                processed = cv2.resize(processed, (new_width, 300), interpolation=cv2.INTER_CUBIC)

            return processed

        except Exception as e:
            logger.error(f"Error en preprocesamiento: {e}")
            return image

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'ocr_test': self.test_ocr
        }

    async def test_ocr(self, update, context):
        """Comando para probar OCR"""
        await update.message.reply_text("📷 OCR plugin activo. Envía un PDF para probar el OCR completo.")

# Instancia global
ocr_plugin = OcrPlugin()
