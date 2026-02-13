#!/usr/bin/env python3
"""
Скрипт для тестирования модуля сравнения фотографий.
Позволяет проверить качество работы алгоритма на тестовых фото.
"""

import os
import sys
import photo_compare
import face_recognition_module
from photo_capture import validate_face

def test_comparison(photo1_path: str, photo2_path: str):
    """
    Тестирует сравнение двух фотографий.
    
    Args:
        photo1_path: путь к первому фото
        photo2_path: путь ко второму фото
    """
    print("=" * 60)
    print("ТЕСТ СРАВНЕНИЯ ФОТОГРАФИЙ")
    print("=" * 60)
    
    # Проверка существования файлов
    if not os.path.exists(photo1_path):
        print(f"❌ Файл не найден: {photo1_path}")
        return
    
    if not os.path.exists(photo2_path):
        print(f"❌ Файл не найден: {photo2_path}")
        return
    
    print(f"\n📷 Фото 1: {photo1_path}")
    print(f"📷 Фото 2: {photo2_path}")
    
    # Проверка лиц
    print("\n🔍 Проверка наличия лиц...")
    try:
        face1_ok = validate_face(photo1_path)
        print(f"  Фото 1: {'✅ Лицо обнаружено' if face1_ok else '❌ Лицо НЕ обнаружено'}")
    except Exception as e:
        print(f"  Фото 1: ❌ Ошибка - {e}")
        face1_ok = False
    
    try:
        face2_ok = validate_face(photo2_path)
        print(f"  Фото 2: {'✅ Лицо обнаружено' if face2_ok else '❌ Лицо НЕ обнаружено'}")
    except Exception as e:
        print(f"  Фото 2: ❌ Ошибка - {e}")
        face2_ok = False
    
    if not (face1_ok and face2_ok):
        print("\n⚠️ На одном или обоих фото не обнаружено лиц!")
        print("   Результаты сравнения могут быть неточными.\n")
    
    # Сравнение
    print("\n🔬 Сравнение фотографий...")
    try:
        # Новый улучшенный метод распознавания лиц
        print("   Метод: Face Recognition Module (извлечение лица + LBP)")
        score = face_recognition_module.compare_faces_advanced(photo1_path, photo2_path)
        print(f"\n📊 РЕЗУЛЬТАТ: {score:.2f}%")
        
        # Интерпретация
        if score >= 90:
            verdict = "🟢 ОТЛИЧНОЕ совпадение - определенно один человек"
        elif score >= 75:
            verdict = "🟡 ХОРОШЕЕ совпадение - скорее всего один человек"
        elif score >= 60:
            verdict = "🟠 СРЕДНЕЕ совпадение - возможно один человек"
        elif score >= 40:
            verdict = "🟤 СЛАБОЕ совпадение - вероятно разные люди"
        else:
            verdict = "🔴 ПЛОХОЕ совпадение - определенно разные люди"
        
        print(f"   {verdict}")
        
        # Детальные метрики (старый метод для сравнения)
        print("\n📋 Детальные метрики (старый метод для сравнения):")
        try:
            comparator = photo_compare.ImageComparator(photo1_path, photo2_path)
            
            ssim = comparator.ssim_comparison()
            hist = comparator.histogram_comparison('correlation')
            phash = comparator.perceptual_hash_comparison('perceptual')
            features = comparator.feature_matching_comparison('orb')
            cosine = comparator.cosine_similarity_pixels()
            
            print(f"   • SSIM (структурное сходство):     {ssim:.3f}")
            print(f"   • Гистограммы (correlation):       {hist:.3f}")
            print(f"   • Perceptual Hash (расстояние):    {phash:.1f}")
            print(f"   • Feature Matching (совпадений):   {features}")
            print(f"   • Cosine Similarity:               {cosine:.3f}")
        except:
            print("   (Старый метод недоступен)")
        
        # Порог
        threshold = 70.0
        print(f"\n⚙️  Порог регистрации: {threshold}%")
        if score >= threshold:
            print("   ✅ Пользователь БУДЕТ зарегистрирован")
        else:
            print("   ❌ Пользователь НЕ БУДЕТ зарегистрирован")
        
    except Exception as e:
        print(f"\n❌ Ошибка при сравнении: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60 + "\n")


def main():
    """Главная функция скрипта."""
    if len(sys.argv) != 3:
        print("Использование:")
        print(f"  python {sys.argv[0]} <фото1.jpg> <фото2.jpg>")
        print("\nПример:")
        print(f"  python {sys.argv[0]} uploads/person1.jpg uploads/person2.jpg")
        sys.exit(1)
    
    photo1 = sys.argv[1]
    photo2 = sys.argv[2]
    
    test_comparison(photo1, photo2)


if __name__ == "__main__":
    main()
