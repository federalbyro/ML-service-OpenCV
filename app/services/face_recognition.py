"""
Модуль высокоточного распознавания лиц.
Использует библиотеку face_recognition (dlib) для создания face embeddings.
Точность: ~99.38% на датасете Labeled Faces in the Wild.
"""

import face_recognition
import numpy as np
from typing import Optional, Tuple, List


class FaceRecognizer:
    """
    Класс для высокоточного распознавания и сравнения лиц.
    
    Использует deep learning модели для:
    - Детекции лиц (HOG или CNN)
    - Извлечения 68 лицевых ориентиров (landmarks)
    - Создания 128D face embedding вектора
    
    Face embedding фокусируется ТОЛЬКО на чертах лица, игнорируя:
    - Фон, Волосы, Одежду, Освещение, Угол поворота
    """
    
    def __init__(self, model: str = "hog", tolerance: float = 0.8):
        """
        Инициализация распознавателя лиц.
        
        Args:
            model: Модель детекции ('hog' - быстрая, 'cnn' - точная, требует GPU)
            tolerance: Порог для сравнения лиц (0.8 = очень мягкий, 0.6 = стандарт, 0.5 = строгий)
        """
        self.model = model
        self.tolerance = tolerance
        
        try:
            test_array = np.zeros((100, 100, 3), dtype=np.uint8)
            _ = face_recognition.face_locations(test_array, model=self.model)
        except Exception as e:
            raise RuntimeError(
                f"Ошибка инициализации face_recognition: {e}\n"
                "Убедитесь что библиотека установлена: pip install face_recognition"
            )
    
    def load_image(self, image_path: str) -> np.ndarray:
        """Загружает изображение в формате RGB (face_recognition требует RGB)."""
        try:
            image = face_recognition.load_image_file(image_path)
            return image
        except Exception as e:
            raise ValueError(f"Не удалось загрузить изображение {image_path}: {e}")
    
    def get_face_encoding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Извлекает face encoding (128D вектор черт лица) из изображения.
        
        Face encoding содер жит уникальные характеристики лица:
        - Расстояние между глазами
        - Форма подбородка, носа
        - И т.д. (всего 128 измерений)
        
        Args:
            image_path: путь к изображению
            
        Returns:
            128D numpy array с face encoding или None если лицо не найдено
        """
        image = self.load_image(image_path)
        face_encodings = face_recognition.face_encodings(image, model=self.model)
        
        if len(face_encodings) == 0:
            return None
        
        return face_encodings[0]
    
    def get_face_locations(self, image_path: str) -> List[Tuple[int, int, int, int]]:
        """Находит координаты лиц на изображении."""
        image = self.load_image(image_path)
        face_locations = face_recognition.face_locations(image, model=self.model)
        return face_locations
    
    def compare_encodings(self, encoding1: np.ndarray, encoding2: np.ndarray) -> float:
        """
        Сравнивает два face encoding и возвращает процент совпадения.
        
        Использует евклидово расстояние между 128D векторами.
        
        Args:
            encoding1: первый face encoding (128D вектор)
            encoding2: второй face encoding (128D вектор)
            
        Returns:
            процент совпадения (0-100)
        """
        distance = face_recognition.face_distance([encoding1], encoding2)[0]
        
        # Конвертируем расстояние в процент совпадения
        # distance = 0 -> 100%, distance = 1 -> 0%
        if distance <= self.tolerance:
            similarity = (1.0 - (distance / self.tolerance)) * 100.0
        else:
            excess = distance - self.tolerance
            similarity = max(0, 40.0 * (1.0 - excess))
        
        return float(min(100.0, max(0.0, similarity)))
    
    def compare_faces_from_files(self, image_path1: str, image_path2: str) -> Tuple[bool, float]:
        """Сравнивает лица на двух фотографиях."""
        encoding1 = self.get_face_encoding(image_path1)
        encoding2 = self.get_face_encoding(image_path2)
        
        if encoding1 is None:
            raise ValueError(f"Лицо не найдено на изображении: {image_path1}")
        if encoding2 is None:
            raise ValueError(f"Лицо не найдено на изображении: {image_path2}")
        
        similarity = self.compare_encodings(encoding1, encoding2)
        
        THRESHOLD = 55.0  # Очень мягкий порог для большей вероятности совпадения
        match = similarity >= THRESHOLD
        
        return match, similarity
    
    def find_best_match(self, 
                       query_image_path: str, 
                       reference_encodings: List[Tuple[int, str, np.ndarray]]) -> Optional[Tuple[int, str, float]]:
        """
        Находит наиболее похожее лицо из списка эталонных encodings.
        
        Args:
            query_image_path: путь к фото для поиска
            reference_encodings: список (id, name, encoding) эталонных лиц
            
        Returns:
            (id, name, similarity) лучшего совпадения или None если нет совпадений
        """
        query_encoding = self.get_face_encoding(query_image_path)
        
        if query_encoding is None:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for person_id, name, ref_encoding in reference_encodings:
            similarity = self.compare_encodings(query_encoding, ref_encoding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = (person_id, name, similarity)
        
        if best_similarity >= 70.0:
            return best_match
        
        return None


# === Публичные функции для совместимости ===

_recognizer = None

def get_recognizer() -> FaceRecognizer:
    """Получить глобальный экземпляр распознавателя (singleton)."""
    global _recognizer
    if _recognizer is None:
        _recognizer = FaceRecognizer()
    return _recognizer


def compare_faces_advanced(image_path1: str, image_path2: str) -> float:
    """
    Сравнивает лица на двух фотографиях и возвращает процент совпадения.
    
    Использует deep learning для извлечения черт лица и их сравнения.
    Фокусируется ТОЛЬКО на чертах лица, игнорируя фон, волосы, одежду.
    
    Args:
        image_path1: путь к первому фото
        image_path2: путь ко второму фото
        
    Returns:
        процент совпадения (0-100)
    """
    recognizer = get_recognizer()
    
    try:
        match, similarity = recognizer.compare_faces_from_files(image_path1, image_path2)
        return similarity
    except ValueError:
        return 0.0
    except Exception as e:
        print(f"Ошибка при сравнении лиц: {e}")
        return 0.0
