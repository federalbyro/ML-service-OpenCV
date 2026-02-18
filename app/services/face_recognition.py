# app/services/face_recognition.py
from __future__ import annotations
from typing import Optional
import numpy as np
import cv2
import os

# Пытаемся импортировать face_recognition (dlib-based)
try:
    import face_recognition as fr
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

# Пытаемся импортировать MediaPipe (fallback)
try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    from mediapipe import Image as MPImage
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False


# Windows short-path fix
def _to_short_path(path: str) -> str:
    """Конвертирует путь в DOS 8.3 формат для MediaPipe"""
    if os.name != "nt":
        return path
    try:
        import ctypes
        from ctypes import wintypes
        
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathNameW.restype = wintypes.DWORD
        
        buf = ctypes.create_unicode_buffer(4096)
        res = GetShortPathNameW(path, buf, 4096)
        return buf.value if res else path
    except Exception:
        return path


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, "models", "face_landmarker.task")

_face_landmarker: Optional['vision.FaceLandmarker'] = None


def _get_face_landmarker():
    """Инициализирует детектор ключевых точек лица"""
    global _face_landmarker
    
    if not MEDIAPIPE_AVAILABLE:
        raise RuntimeError("MediaPipe не установлен")
    
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"Модель не найдена: {MODEL_PATH}")
    
    if _face_landmarker is None:
        model_short = _to_short_path(MODEL_PATH)
        base_options = python.BaseOptions(model_asset_path=model_short)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1
        )
        _face_landmarker = vision.FaceLandmarker.create_from_options(options)
    
    return _face_landmarker


def validate_face_one(image_path: str) -> bool:
    """Проверяет наличие ровно одного лица на фото"""
    
    # Приоритет: face_recognition (более точный)
    if FACE_RECOGNITION_AVAILABLE:
        try:
            image = fr.load_image_file(image_path)
            face_locations = fr.face_locations(image, model="hog")  # hog быстрее, cnn точнее
            return len(face_locations) == 1
        except Exception as e:
            print(f"face_recognition validation failed: {e}")
    
    # Fallback: MediaPipe
    if MEDIAPIPE_AVAILABLE and os.path.exists(MODEL_PATH):
        try:
            landmarker = _get_face_landmarker()
            bgr = cv2.imread(image_path)
            if bgr is None:
                return False
            
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            mp_image = MPImage(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
            
            return (result is not None) and (len(result.face_landmarks) == 1)
        except:
            pass
    
    # Fallback: OpenCV
    try:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        img = cv2.imread(image_path)
        if img is None:
            return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
        return len(faces) == 1
    except:
        return False


def _extract_face_region_features(image: np.ndarray, landmarks) -> np.ndarray:
    """
    Извлекает текстурные признаки из ключевых областей лица
    Это то, что делает лица уникальными!
    """
    h, w = image.shape[:2]
    
    # Конвертируем landmarks в пиксельные координаты
    points = []
    for lm in landmarks:
        x = int(lm.x * w)
        y = int(lm.y * h)
        points.append((x, y))
    
    # Ключевые области для текстурных признаков:
    # Левый глаз: landmarks 33, 133, 160, 159, 158, 157, 173
    # Правый глаз: landmarks 362, 263, 387, 386, 385, 384, 398
    # Нос: landmarks 1, 2, 98, 327
    # Рот: landmarks 61, 291, 13, 14
    
    left_eye_indices = [33, 133, 160, 159, 158, 157, 173]
    right_eye_indices = [362, 263, 387, 386, 385, 384, 398]
    nose_indices = [1, 2, 98, 327, 195, 5]
    mouth_indices = [61, 291, 13, 14, 78, 308]
    
    features = []
    
    # Для каждой области извлекаем текстурные признаки
    for region_indices, region_name in [
        (left_eye_indices, "left_eye"),
        (right_eye_indices, "right_eye"),
        (nose_indices, "nose"),
        (mouth_indices, "mouth")
    ]:
        # Получаем bounding box области
        region_points = [points[i] for i in region_indices if i < len(points)]
        if not region_points:
            features.extend([0.0] * 128)  # Заполнитель
            continue
        
        xs = [p[0] for p in region_points]
        ys = [p[1] for p in region_points]
        
        x_min, x_max = max(0, min(xs) - 10), min(w, max(xs) + 10)
        y_min, y_max = max(0, min(ys) - 10), min(h, max(ys) + 10)
        
        if x_max <= x_min or y_max <= y_min:
            features.extend([0.0] * 128)
            continue
        
        # Извлекаем область
        region = image[y_min:y_max, x_min:x_max]
        
        if region.size == 0:
            features.extend([0.0] * 128)
            continue
        
        # Нормализуем размер
        region_resized = cv2.resize(region, (64, 64))
        gray_region = cv2.cvtColor(region_resized, cv2.COLOR_BGR2GRAY) if len(region_resized.shape) == 3 else region_resized
        
        # LBP признаки (текстура)
        lbp = _compute_simple_lbp(gray_region)
        lbp_hist, _ = np.histogram(lbp.ravel(), bins=32, range=(0, 256))
        lbp_hist = lbp_hist.astype(np.float32)
        lbp_hist /= (lbp_hist.sum() + 1e-7)
        
        # Градиентные признаки
        gx = cv2.Sobel(gray_region, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(gray_region, cv2.CV_32F, 0, 1)
        grad_mag = np.sqrt(gx**2 + gy**2)
        grad_hist, _ = np.histogram(grad_mag.ravel(), bins=16, range=(0, 255))
        grad_hist = grad_hist.astype(np.float32)
        grad_hist /= (grad_hist.sum() + 1e-7)
        
        # Цветовые признаки (HSV)
        hsv = cv2.cvtColor(region_resized, cv2.COLOR_BGR2HSV)
        h_hist = cv2.calcHist([hsv], [0], None, [16], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [16], [0, 256])
        color_hist = np.concatenate([h_hist.flatten(), s_hist.flatten()])
        color_hist = color_hist.astype(np.float32)
        color_hist /= (color_hist.sum() + 1e-7)
        
        # Комбинируем признаки региона
        region_features = np.concatenate([lbp_hist, grad_hist, color_hist])
        features.extend(region_features)
    
    return np.array(features, dtype=np.float32)


def _compute_simple_lbp(image: np.ndarray) -> np.ndarray:
    """Простой LBP 3x3"""
    lbp = np.zeros_like(image, dtype=np.uint8)
    for i in range(1, image.shape[0] - 1):
        for j in range(1, image.shape[1] - 1):
            center = image[i, j]
            code = 0
            code |= (image[i-1, j-1] >= center) << 7
            code |= (image[i-1, j] >= center) << 6
            code |= (image[i-1, j+1] >= center) << 5
            code |= (image[i, j+1] >= center) << 4
            code |= (image[i+1, j+1] >= center) << 3
            code |= (image[i+1, j] >= center) << 2
            code |= (image[i+1, j-1] >= center) << 1
            code |= (image[i, j-1] >= center) << 0
            lbp[i, j] = code
    return lbp


def get_embedding(image_path: str) -> Optional[np.ndarray]:
    """Извлекает эмбеддинг лица используя deep learning (face_recognition/dlib)"""
    
    # Используем face_recognition (dlib) - предобученная нейросеть
    if FACE_RECOGNITION_AVAILABLE:
        try:
            # Загружаем изображение
            image = fr.load_image_file(image_path)
            
            # Находим лица
            face_locations = fr.face_locations(image, model="hog")
            
            if len(face_locations) != 1:
                return None
            
            # Получаем 128-мерный вектор признаков
            # Это предобученная нейросеть, которая выучила различать лица
            face_encodings = fr.face_encodings(image, face_locations, num_jitters=1)
            
            if len(face_encodings) != 1:
                return None
            
            embedding = face_encodings[0]
            
            # Уже нормализован
            return embedding.astype(np.float32)
            
        except Exception as e:
            print(f"Ошибка face_recognition: {e}")
            return None
    
    # Fallback: используем старый метод с MediaPipe + текстура
    # (если face_recognition не установлен)
    if not MEDIAPIPE_AVAILABLE or not os.path.exists(MODEL_PATH):
        return None
    
    try:
        landmarker = _get_face_landmarker()
        
        bgr = cv2.imread(image_path)
        if bgr is None:
            return None
        
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_image = MPImage(image_format=mp.ImageFormat.SRGB, data=rgb)
        
        result = landmarker.detect(mp_image)

        if result is None or len(result.face_landmarks) != 1:
            return None

        landmarks = result.face_landmarks[0]
        
        # Используем текстурные признаки (старый метод)
        h, w = bgr.shape[:2]
        
        def extract_region_features_simple(region_landmarks_indices):
            """Простое извлечение признаков"""
            points = []
            for idx in region_landmarks_indices:
                if idx < len(landmarks):
                    lm = landmarks[idx]
                    points.append((int(lm.x * w), int(lm.y * h)))
            
            if not points:
                return np.zeros(64, dtype=np.float32)
            
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x_min, x_max = max(0, min(xs) - 10), min(w, max(xs) + 10)
            y_min, y_max = max(0, min(ys) - 10), min(h, max(ys) + 10)
            
            if x_max <= x_min or y_max <= y_min:
                return np.zeros(64, dtype=np.float32)
            
            region = bgr[y_min:y_max, x_min:x_max]
            if region.size == 0:
                return np.zeros(64, dtype=np.float32)
            
            region_resized = cv2.resize(region, (32, 32))
            gray = cv2.cvtColor(region_resized, cv2.COLOR_BGR2GRAY)
            
            # Простые признаки
            hist, _ = np.histogram(gray.ravel(), bins=64, range=(0, 256))
            hist = hist.astype(np.float32) / (hist.sum() + 1e-7)
            
            return hist
        
        # Основные области
        features = []
        features.extend(extract_region_features_simple(list(range(33, 42))))  # левый глаз
        features.extend(extract_region_features_simple(list(range(263, 272))))  # правый глаз
        features.extend(extract_region_features_simple(list(range(1, 20))))  # нос
        features.extend(extract_region_features_simple(list(range(61, 80))))  # рот
        
        embedding = np.array(features, dtype=np.float32)
        embedding /= (np.linalg.norm(embedding) + 1e-12)
        
        return embedding
        
    except Exception as e:
        print(f"Ошибка get_embedding: {e}")
        return None


def compare_faces_advanced(image_path1: str, image_path2: str) -> float:
    """Сравнивает два лица используя deep learning эмбеддинги"""
    try:
        e1 = get_embedding(image_path1)
        e2 = get_embedding(image_path2)
        
        if e1 is None or e2 is None:
            return 0.0

        # Косинусное сходство
        cos_sim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-12))
        
        # Евклидово расстояние
        euclidean_dist = float(np.linalg.norm(e1 - e2))
        
        # Пороги для face_recognition (128-мерные эмбеддинги от dlib)
        # Стандартный порог для face_recognition - расстояние 0.6
        # Преобразуем в проценты для удобства
        
        if FACE_RECOGNITION_AVAILABLE:
            # face_recognition использует Euclidean distance
            # Типичные значения:
            # < 0.4  = очень похожи (один человек)
            # 0.4-0.6 = похожи (возможно один человек)
            # > 0.6  = разные люди
            
            # Преобразуем в проценты (инвертированная логика для расстояния)
            if euclidean_dist < 0.4:
                percentage = 100.0 - (euclidean_dist / 0.4) * 10.0  # 90-100%
            elif euclidean_dist < 0.6:
                percentage = 90.0 - ((euclidean_dist - 0.4) / 0.2) * 40.0  # 50-90%
            elif euclidean_dist < 1.0:
                percentage = 50.0 - ((euclidean_dist - 0.6) / 0.4) * 50.0  # 0-50%
            else:
                percentage = 0.0
            
            percentage = max(0.0, min(100.0, percentage))
            
            print(f"Eucl: {euclidean_dist:.4f}, Cos: {cos_sim:.4f} -> {percentage:.1f}%")
        else:
            # Fallback: используем косинусное сходство для старого метода
            threshold_very_low = 0.75
            threshold_low = 0.88
            threshold_high = 0.94
            threshold_perfect = 0.97
            
            if cos_sim < threshold_very_low:
                percentage = 0.0
            elif cos_sim < threshold_low:
                normalized = (cos_sim - threshold_very_low) / (threshold_low - threshold_very_low)
                percentage = normalized * 50.0
            elif cos_sim < threshold_high:
                normalized = (cos_sim - threshold_low) / (threshold_high - threshold_low)
                percentage = 50.0 + normalized * 40.0
            elif cos_sim < threshold_perfect:
                normalized = (cos_sim - threshold_high) / (threshold_perfect - threshold_high)
                percentage = 90.0 + normalized * 10.0
            else:
                percentage = 100.0
            
            percentage = max(0.0, min(100.0, percentage))
            
            print(f"Cos: {cos_sim:.4f}, Eucl: {euclidean_dist:.4f} -> {percentage:.1f}%")
        
        return float(percentage)
        
    except Exception as e:
        print(f"Ошибка compare_faces_advanced: {e}")
        return 0.0