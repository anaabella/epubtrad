"""
Plugin de sistema de recomendaciones basado en historial de traducciones
"""
import os
import logging
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Tuple
import json

logger = logging.getLogger(__name__)

class RecommendationPlugin:
    def __init__(self):
        self.name = "recommendation"
        self.description = "Sistema de recomendaciones basado en historial de traducciones"
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.tfidf_matrix = None
        self.book_titles = []
        self.book_metadata = {}

    def register_hooks(self, plugin_manager):
        """Registrar hooks para el sistema de plugins"""
        plugin_manager.register_hook('post_translation', self.on_post_translation)
        plugin_manager.register_hook('user_request', self.on_user_request)

    def on_post_translation(self, user_id: int, titulo: str, capitulos: List[Tuple[str, str]], formato: str):
        """Hook ejecutado después de una traducción completa"""
        try:
            # Actualizar base de datos de libros
            self.update_book_database(titulo, capitulos)
            logger.info(f"Base de datos de recomendaciones actualizada con: {titulo}")
        except Exception as e:
            logger.error(f"Error actualizando recomendaciones: {e}")

    def on_user_request(self, user_id: int, request_type: str):
        """Hook para solicitudes de usuario"""
        if request_type == 'recommendations':
            return self.get_recommendations(user_id)

    def update_book_database(self, titulo: str, capitulos: List[Tuple[str, str]]):
        """Actualizar la base de datos de libros para recomendaciones"""
        try:
            # Extraer texto completo
            full_text = ""
            for cap_nombre, cap_texto in capitulos:
                full_text += f"{cap_nombre} {cap_texto} "

            # Guardar metadata
            if titulo not in self.book_titles:
                self.book_titles.append(titulo)
                self.book_metadata[titulo] = {
                    'text': full_text[:10000],  # Limitar texto
                    'chapters': len(capitulos),
                    'word_count': len(full_text.split())
                }

            # Regenerar matriz TF-IDF
            if len(self.book_titles) > 1:
                texts = [self.book_metadata[title]['text'] for title in self.book_titles]
                self.tfidf_matrix = self.vectorizer.fit_transform(texts)

            # Guardar en archivo
            self.save_database()

        except Exception as e:
            logger.error(f"Error actualizando base de datos: {e}")

    def get_recommendations(self, user_id: int) -> List[str]:
        """Obtener recomendaciones para un usuario"""
        try:
            from main import historial

            if user_id not in historial or not historial[user_id]:
                return ["Traduce algunos libros primero para obtener recomendaciones personalizadas."]

            # Obtener libros recientes del usuario
            user_books = [titulo for titulo, _ in historial[user_id]]

            if not self.tfidf_matrix or len(self.book_titles) < 2:
                return ["Se necesitan más libros en la base de datos para generar recomendaciones."]

            recommendations = []

            for user_book in user_books[-3:]:  # Últimos 3 libros
                if user_book in self.book_titles:
                    book_idx = self.book_titles.index(user_book)
                    similarities = cosine_similarity(self.tfidf_matrix[book_idx], self.tfidf_matrix).flatten()

                    # Obtener índices de libros más similares (excluyendo el mismo libro)
                    similar_indices = similarities.argsort()[::-1][1:4]  # Top 3 similares

                    for idx in similar_indices:
                        similar_book = self.book_titles[idx]
                        if similar_book not in user_books and similar_book not in recommendations:
                            recommendations.append(similar_book)

            if recommendations:
                return recommendations[:5]  # Máximo 5 recomendaciones
            else:
                return ["No se encontraron recomendaciones similares en este momento."]

        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
            return ["Error generando recomendaciones."]

    def save_database(self):
        """Guardar base de datos de libros"""
        try:
            os.makedirs('storage', exist_ok=True)
            data = {
                'book_titles': self.book_titles,
                'book_metadata': self.book_metadata
            }
            with open('storage/book_database.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando base de datos: {e}")

    def load_database(self):
        """Cargar base de datos de libros"""
        try:
            if os.path.exists('storage/book_database.json'):
                with open('storage/book_database.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.book_titles = data.get('book_titles', [])
                    self.book_metadata = data.get('book_metadata', {})

                # Regenerar matriz TF-IDF si hay datos
                if self.book_titles:
                    texts = [self.book_metadata[title]['text'] for title in self.book_titles]
                    self.tfidf_matrix = self.vectorizer.fit_transform(texts)

                logger.info(f"Base de datos cargada: {len(self.book_titles)} libros")
        except Exception as e:
            logger.error(f"Error cargando base de datos: {e}")

    def get_commands(self):
        """Comandos que este plugin agrega"""
        return {
            'recommend': self.show_recommendations
        }

    async def show_recommendations(self, update, context):
        """Mostrar recomendaciones personalizadas"""
        user_id = update.message.from_user.id

        recommendations = self.get_recommendations(user_id)

        if recommendations:
            msg = "📚 Recomendaciones basadas en tu historial:\n\n"
            for i, book in enumerate(recommendations, 1):
                msg += f"{i}. {book}\n"
            msg += "\n💡 Estas recomendaciones se basan en similitudes de contenido con los libros que has traducido."
        else:
            msg = "📚 No hay suficientes datos para generar recomendaciones. Traduce algunos libros más primero."

        await update.message.reply_text(msg)

# Cargar base de datos al inicializar
recommendation_plugin = RecommendationPlugin()
recommendation_plugin.load_database()
