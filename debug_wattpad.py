#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

def debug_wattpad():
    url = "https://www.wattpad.com/969099212-the-way-i-hate-you-park-sunghoon-chapter-1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    print("=== Buscando párrafos ===")
    paragraphs = soup.find_all('p')
    print(f"Total párrafos encontrados: {len(paragraphs)}")

    story_paragraphs = []
    for i, p in enumerate(paragraphs):
        text = p.get_text().strip()
        if text and len(text) > 20 and not any(skip in text.lower() for skip in ['you are reading', 'fanfiction', '#']):
            story_paragraphs.append(text)
            print(f"P{i+1}: {text[:150]}...")

    print(f"\nPárrafos de historia encontrados: {len(story_paragraphs)}")

    print("\n=== Buscando divs con clases relacionadas ===")
    classes_to_check = ['story-text', 'panel-reading', 'chapter-content', 'text', 'content']
    for class_name in classes_to_check:
        divs = soup.find_all('div', class_=class_name)
        print(f"Divs con clase '{class_name}': {len(divs)}")
        for div in divs[:2]:
            text = div.get_text().strip()
            print(f"  Contenido: {text[:200]}...")

    print("\n=== Buscando elementos con data attributes ===")
    data_divs = soup.find_all(attrs={'data-text': True})
    print(f"Elementos con data-text: {len(data_divs)}")
    for div in data_divs[:2]:
        text = div.get_text().strip()
        print(f"  Contenido: {text[:200]}...")

    print("\n=== Buscando pre tags ===")
    pre_tags = soup.find_all('pre')
    print(f"Pre tags: {len(pre_tags)}")
    for pre in pre_tags[:2]:
        text = pre.get_text().strip()
        print(f"  Contenido: {text[:200]}...")

    print("\n=== Intentando extraer contenido de historia ===")
    # Filtrar párrafos que parecen ser contenido de la historia
    content_paragraphs = []
    for p in paragraphs:
        text = p.get_text().strip()
        if text and len(text) > 30:
            # Excluir párrafos que contienen elementos de UI o metadatos
            if not any(skip in text.lower() for skip in [
                'you are reading', 'fanfiction', 'read', 'vote', 'comment', 'share',
                'chapter', 'author', 'published', 'updated', 'views', 'votes'
            ]):
                # Excluir líneas que son solo hashtags
                if not re.match(r'^#\w+', text):
                    content_paragraphs.append(text)

    print(f"Párrafos de contenido filtrados: {len(content_paragraphs)}")
    for i, p in enumerate(content_paragraphs[:5]):
        print(f"Contenido {i+1}: {p[:200]}...")

    if content_paragraphs:
        full_content = '\n'.join(content_paragraphs)
        print(f"\nContenido completo extraído ({len(full_content)} caracteres):")
        print(full_content[:500] + "...")

if __name__ == "__main__":
    debug_wattpad()
