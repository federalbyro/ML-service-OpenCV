import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from scipy.spatial import distance
import imagehash
from PIL import Image

class ImageComparator:
    """Класс для сравнения двух изображений различными методами."""
    
    def __init__(self, image_path1, image_path2):
        """
        Инициализация сравнителя изображений.
        
        Args:
            image_path1: путь к первому изображению
            image_path2: путь ко второму изображению
        """
        self.image_path1 = image_path1
        self.image_path2 = image_path2
        
        # Загрузка изображений
        self.img1_cv = cv2.imread(image_path1)
        self.img2_cv = cv2.imread(image_path2)
        
        if self.img1_cv is None or self.img2_cv is None:
            raise ValueError("Не удалось загрузить одно или оба изображения")
        
        # Для PIL (нужно для перцептуального хеширования)
        self.img1_pil = Image.open(image_path1)
        self.img2_pil = Image.open(image_path2)
    
    def mse_comparison(self):
        """
        Сравнение по среднеквадратичной ошибке (MSE).
        Чем меньше значение, тем более похожи изображения.
        0 = идентичные изображения.
        
        Returns:
            float: значение MSE
        """
        # Приведение к одинаковому размеру
        img1_resized = cv2.resize(self.img1_cv, (300, 300))
        img2_resized = cv2.resize(self.img2_cv, (300, 300))
        
        # Вычисление MSE
        mse = np.mean((img1_resized.astype(float) - img2_resized.astype(float)) ** 2)
        return mse
    
    def ssim_comparison(self):
        """
        Структурное сравнение изображений (SSIM).
        Диапазон: от -1 до 1, где 1 = идентичные изображения.
        
        Returns:
            float: индекс структурного сходства
        """
        # Приведение к одинаковому размеру и grayscale
        img1_gray = cv2.cvtColor(self.img1_cv, cv2.COLOR_BGR2GRAY)
        img2_gray = cv2.cvtColor(self.img2_cv, cv2.COLOR_BGR2GRAY)
        
        img1_resized = cv2.resize(img1_gray, (300, 300))
        img2_resized = cv2.resize(img2_gray, (300, 300))
        
        # Вычисление SSIM
        similarity_index, _ = ssim(img1_resized, img2_resized, full=True)
        return similarity_index
    
    def histogram_comparison(self, method='correlation'):
        """
        Сравнение изображений по гистограммам цветов.
        
        Args:
            method: метод сравнения ('correlation', 'chi_square', 'intersection', 'bhattacharyya')
        
        Returns:
            float: мера сходства (зависит от метода)
        """
        # Приведение к одинаковому размеру
        img1_resized = cv2.resize(self.img1_cv, (300, 300))
        img2_resized = cv2.resize(self.img2_cv, (300, 300))
        
        # Вычисление гистограмм для каждого канала
        hist1 = cv2.calcHist([img1_resized], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist2 = cv2.calcHist([img2_resized], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        
        # Нормализация
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()
        
        # Сравнение гистограмм
        method_map = {
            'correlation': cv2.HISTCMP_CORREL,  # 1 = идентичные
            'chi_square': cv2.HISTCMP_CHISQR,   # 0 = идентичные
            'intersection': cv2.HISTCMP_INTERSECT,  # больше = более похожи
            'bhattacharyya': cv2.HISTCMP_BHATTACHARYYA  # 0 = идентичные
        }
        
        comparison_method = method_map.get(method, cv2.HISTCMP_CORREL)
        similarity = cv2.compareHist(hist1.reshape(-1, 1), hist2.reshape(-1, 1), comparison_method)
        
        return similarity
    
    def perceptual_hash_comparison(self, hash_type='average'):
        """
        Сравнение изображений с использованием перцептуального хеширования.
        Возвращает расстояние Хэмминга между хешами.
        0 = идентичные изображения, больше = менее похожи.
        
        Args:
            hash_type: тип хеша ('average', 'perceptual', 'difference', 'wavelet')
        
        Returns:
            int: расстояние Хэмминга
        """
        hash_functions = {
            'average': imagehash.average_hash,
            'perceptual': imagehash.phash,
            'difference': imagehash.dhash,
            'wavelet': imagehash.whash
        }
        
        hash_func = hash_functions.get(hash_type, imagehash.average_hash)
        
        hash1 = hash_func(self.img1_pil)
        hash2 = hash_func(self.img2_pil)
        
        return hash1 - hash2  # Расстояние Хэмминга
    
    def feature_matching_comparison(self, method='orb'):
        """
        Сравнение изображений по ключевым точкам (feature matching).
        Возвращает количество совпадающих признаков.
        
        Args:
            method: метод детекции признаков ('orb', 'sift')
        
        Returns:
            int: количество хороших совпадений
        """
        # Конвертация в grayscale
        img1_gray = cv2.cvtColor(self.img1_cv, cv2.COLOR_BGR2GRAY)
        img2_gray = cv2.cvtColor(self.img2_cv, cv2.COLOR_BGR2GRAY)
        
        # Выбор детектора признаков
        if method == 'sift':
            try:
                detector = cv2.SIFT_create()
            except AttributeError:
                # Если SIFT недоступен, используем ORB
                detector = cv2.ORB_create()
        else:
            detector = cv2.ORB_create()
        
        # Поиск ключевых точек и дескрипторов
        kp1, des1 = detector.detectAndCompute(img1_gray, None)
        kp2, des2 = detector.detectAndCompute(img2_gray, None)
        
        if des1 is None or des2 is None:
            return 0
        
        # Создание матчера
        if method == 'sift':
            bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        else:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # Поиск совпадений
        matches = bf.knnMatch(des1, des2, k=2)
        
        # Применение ratio test (алгоритм Лоу)
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        return len(good_matches)
    
    def cosine_similarity_pixels(self):
        """
        Косинусное сходство между векторами пикселей изображений.
        Диапазон: от -1 до 1, где 1 = идентичные изображения.
        
        Returns:
            float: косинусное сходство
        """
        # Приведение к одинаковому размеру
        img1_resized = cv2.resize(self.img1_cv, (100, 100))
        img2_resized = cv2.resize(self.img2_cv, (100, 100))
        
        # Преобразование в векторы
        vec1 = img1_resized.flatten()
        vec2 = img2_resized.flatten()
        
        # Вычисление косинусного сходства
        cosine_sim = 1 - distance.cosine(vec1, vec2)
        return cosine_sim
    
    def compare_all(self):
        """
        Выполняет все доступные методы сравнения и возвращает результаты.
        
        Returns:
            dict: словарь с результатами всех методов
        """
        results = {
            'MSE': self.mse_comparison(),
            'SSIM': self.ssim_comparison(),
            'Histogram (correlation)': self.histogram_comparison('correlation'),
            'Perceptual Hash (average)': self.perceptual_hash_comparison('average'),
            'Perceptual Hash (perceptual)': self.perceptual_hash_comparison('perceptual'),
            'Perceptual Hash (difference)': self.perceptual_hash_comparison('difference'),
            'Feature Matching (ORB)': self.feature_matching_comparison('orb'),
            'Cosine Similarity': self.cosine_similarity_pixels()
        }
        
        return results
    
    def get_similarity_percentage(self):
        """
        Возвращает общую оценку схожести изображений в процентах.
        Использует комбинацию нескольких метрик.
        
        Returns:
            float: процент схожести (0-100)
        """
        # Получаем основные метрики
        ssim_score = self.ssim_comparison()
        hist_score = self.histogram_comparison('correlation')
        phash_score = self.perceptual_hash_comparison('perceptual')
        cosine_score = self.cosine_similarity_pixels()
        
        # Нормализуем perceptual hash (0-64 -> 1-0)
        phash_normalized = max(0, 1 - (phash_score / 64))
        
        # Усредняем нормализованные метрики
        avg_similarity = (
            ssim_score * 0.3 +          # 30% веса
            hist_score * 0.2 +          # 20% веса
            phash_normalized * 0.3 +    # 30% веса
            cosine_score * 0.2          # 20% веса
        )
        
        # Конвертируем в проценты
        similarity_percentage = max(0, min(100, avg_similarity * 100))
        
        return similarity_percentage


def compare(image_path1: str, image_path2: str, threshold: float = 70.0):
    """
    Совместимость с app.py:
      match, score = photo_compare.compare(path1, path2)

    Возвращает:
      match: bool (True если score >= threshold)
      score: float (0..100)
    """
    comparator = ImageComparator(image_path1, image_path2)
    score = float(comparator.get_similarity_percentage())
    match = score >= float(threshold)
    return match, score