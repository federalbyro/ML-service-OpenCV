"""
Модуль специализированного распознавания лиц.
Использует извлечение области лица, нормализацию и несколько методов сравнения.
"""

import cv2
import numpy as np
from typing import Optional, Tuple
import os

# Путь к каскаду Хаара
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASCADE_PATH = os.path.join(BASE_DIR, "cascades", "haarcascade_frontalface_default.xml")


class FaceRecognizer:
    """Класс для распознавания и сравнения лиц."""
    
    def __init__(self):
        """Инициализация детектора лиц."""
        self.face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if self.face_cascade.empty():
            raise RuntimeError(f"Не удалось загрузить каскад: {CASCADE_PATH}")
        
        # Стандартный размер для нормализации
        self.target_size = (128, 128)
    
    def extract_face(self, image_path: str) -> Optional[np.ndarray]:
        """
        Извлекает область лица из изображения.
        
        Args:
            image_path: путь к изображению
            
        Returns:
            numpy array с областью лица или None если лицо не найдено
        """
        # Загрузка изображения
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Не удалось загрузить изображение: {image_path}")
        
        # Конвертация в grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Детекция лиц
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )
        
        if len(faces) == 0:
            return None
        
        # Берем самое большое лицо (если несколько)
        largest_face = max(faces, key=lambda face: face[2] * face[3])
        x, y, w, h = largest_face
        
        # Добавляем padding 20% для захвата контекста
        padding = int(0.2 * max(w, h))
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.shape[1], x + w + padding)
        y2 = min(img.shape[0], y + h + padding)
        
        # Извлекаем область лица
        face_roi = img[y1:y2, x1:x2]
        
        return face_roi
    
    def preprocess_face(self, face: np.ndarray) -> np.ndarray:
        """
        Предобработка лица: нормализация размера, освещения.
        
        Args:
            face: область лица (BGR)
            
        Returns:
            обработанное лицо
        """
        # Изменение размера
        face_resized = cv2.resize(face, self.target_size)
        
        # Конвертация в grayscale для некоторых операций
        gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
        
        # Нормализация освещения (histogram equalization)
        gray_eq = cv2.equalizeHist(gray)
        
        # Конвертируем обратно в BGR
        face_normalized = cv2.cvtColor(gray_eq, cv2.COLOR_GRAY2BGR)
        
        return face_normalized
    
    def compute_histogram(self, face: np.ndarray) -> np.ndarray:
        """Вычисляет гистограмму цветов лица."""
        # HSV более устойчив к изменениям освещения
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
        
        # Вычисляем гистограмму по каналам H и S (игнорируем V - яркость)
        hist_h = cv2.calcHist([hsv], [0], None, [50], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [60], [0, 256])
        
        # Нормализация
        hist_h = cv2.normalize(hist_h, hist_h).flatten()
        hist_s = cv2.normalize(hist_s, hist_s).flatten()
        
        # Объединяем
        hist_combined = np.concatenate([hist_h, hist_s])
        
        return hist_combined
    
    def compute_lbp_histogram(self, face: np.ndarray) -> np.ndarray:
        """
        Вычисляет LBP (Local Binary Pattern) гистограмму.
        LBP очень эффективен для распознавания лиц.
        """
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Простая реализация LBP
        height, width = gray.shape
        lbp = np.zeros_like(gray)
        
        for i in range(1, height - 1):
            for j in range(1, width - 1):
                center = gray[i, j]
                code = 0
                
                # 8 соседей вокруг центрального пикселя
                code |= (gray[i-1, j-1] >= center) << 7
                code |= (gray[i-1, j] >= center) << 6
                code |= (gray[i-1, j+1] >= center) << 5
                code |= (gray[i, j+1] >= center) << 4
                code |= (gray[i+1, j+1] >= center) << 3
                code |= (gray[i+1, j] >= center) << 2
                code |= (gray[i+1, j-1] >= center) << 1
                code |= (gray[i, j-1] >= center) << 0
                
                lbp[i, j] = code
        
        # Вычисляем гистограмму LBP
        hist = cv2.calcHist([lbp], [0], None, [256], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        
        return hist
    
    def compare_faces(self, face1: np.ndarray, face2: np.ndarray) -> float:
        """
        Сравнивает два лица и возвращает процент совпадения.
        
        Args:
            face1: первое лицо (BGR)
            face2: второе лицо (BGR)
            
        Returns:
            процент совпадения (0-100)
        """
        # Предобработка
        face1_proc = self.preprocess_face(face1)
        face2_proc = self.preprocess_face(face2)
        
        # === Метод 1: SSIM (структурное сходство) ===
        gray1 = cv2.cvtColor(face1_proc, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(face2_proc, cv2.COLOR_BGR2GRAY)
        
        from skimage.metrics import structural_similarity
        ssim_score = structural_similarity(gray1, gray2)
        
        # === Метод 2: Гистограммы HSV ===
        hist1 = self.compute_histogram(face1_proc)
        hist2 = self.compute_histogram(face2_proc)
        hist_correlation = cv2.compareHist(
            hist1.reshape(-1, 1),
            hist2.reshape(-1, 1),
            cv2.HISTCMP_CORREL
        )
        
        # === Метод 3: LBP (Local Binary Patterns) ===
        lbp1 = self.compute_lbp_histogram(face1_proc)
        lbp2 = self.compute_lbp_histogram(face2_proc)
        lbp_correlation = cv2.compareHist(
            lbp1.reshape(-1, 1),
            lbp2.reshape(-1, 1),
            cv2.HISTCMP_CORREL
        )
        
        # === Метод 4: Template Matching ===
        # Нормализованная кросс-корреляция
        result = cv2.matchTemplate(gray1, gray2, cv2.TM_CCORR_NORMED)
        template_score = result[0][0]
        
        # === Метод 5: ORB Feature Matching ===
        orb = cv2.ORB_create(nfeatures=500)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)
        
        if des1 is not None and des2 is not None and len(des1) > 0 and len(des2) > 0:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            
            # Берем топ-30% лучших совпадений
            good_matches = matches[:int(len(matches) * 0.3)]
            
            # Нормализуем количество совпадений (50 = хорошо)
            feature_score = min(1.0, len(good_matches) / 50.0)
        else:
            feature_score = 0.0
        
        # === Взвешенная комбинация ===
        # Оптимизированные веса для распознавания лиц
        weights = {
            'ssim': 0.30,           # Структурное сходство - самое важное
            'hist': 0.15,           # Цветовое распределение
            'lbp': 0.30,            # LBP - очень эффективен для лиц!
            'template': 0.15,       # Template matching
            'features': 0.10        # Feature matching
        }
        
        final_score = (
            ssim_score * weights['ssim'] +
            hist_correlation * weights['hist'] +
            lbp_correlation * weights['lbp'] +
            template_score * weights['template'] +
            feature_score * weights['features']
        )
        
        # Конвертация в проценты
        percentage = max(0, min(100, final_score * 100))
        
        return float(percentage)
    
    def match_face(self, query_image_path: str, reference_image_path: str) -> Tuple[bool, float]:
        """
        Сравнивает лицо на query изображении с reference изображением.
        
        Args:
            query_image_path: путь к фото для проверки
            reference_image_path: путь к эталонному фото
            
        Returns:
            (match: bool, score: float) - совпадение и процент схожести
        """
        # Извлекаем лица
        face1 = self.extract_face(query_image_path)
        face2 = self.extract_face(reference_image_path)
        
        if face1 is None:
            raise ValueError(f"Лицо не найдено на изображении: {query_image_path}")
        if face2 is None:
            raise ValueError(f"Лицо не найдено на изображении: {reference_image_path}")
        
        # Сравниваем
        score = self.compare_faces(face1, face2)
        
        # Порог совпадения
        THRESHOLD = 70.0
        match = score >= THRESHOLD
        
        return match, score


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
    
    Args:
        image_path1: путь к первому фото
        image_path2: путь ко второму фото
        
    Returns:
        процент совпадения (0-100)
    """
    recognizer = get_recognizer()
    
    # Извлекаем лица
    face1 = recognizer.extract_face(image_path1)
    face2 = recognizer.extract_face(image_path2)
    
    if face1 is None or face2 is None:
        # Если лиц нет, возвращаем минимальный score
        return 0.0
    
    # Сравниваем
    score = recognizer.compare_faces(face1, face2)
    
    return score
