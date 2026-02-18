#!/usr/bin/env python3
"""
Простой скрипт для тестирования распознавания лиц.

Использование:
1. Положите две фотографии в папку проекта:
   - photo1.jpg
   - photo2.jpg

2. Запустите:
   python test_face_match.py

ИЛИ укажите свои пути:
   python test_face_match.py path/to/photo1.jpg path/to/photo2.jpg
"""

import sys
import os
from app.services import face_recognition

def test_face_recognition(photo1_path, photo2_path):
    """Сравнивает два фото и выводит результат."""
    
    print("=" * 60)
    print("🔍 ТЕСТИРОВАНИЕ РАСПОЗНАВАНИЯ ЛИЦ")
    print("=" * 60)
    
    # Проверяем существование файлов
    if not os.path.exists(photo1_path):
        print(f"❌ Ошибка: Файл не найден: {photo1_path}")
        return
    
    if not os.path.exists(photo2_path):
        print(f"❌ Ошибка: Файл не найден: {photo2_path}")
        return
    
    print(f"\n📸 Фото 1: {photo1_path}")
    print(f"📸 Фото 2: {photo2_path}")
    print("\n⏳ Анализирую лица...")
    
    try:
        # Сравниваем фотографии
        score = face_recognition.compare_faces_advanced(photo1_path, photo2_path)
        
        print(f"\n{'=' * 60}")
        print(f"📊 РЕЗУЛЬТАТ: {score:.1f}%")
        print(f"{'=' * 60}\n")
        
        # Интерпретация результата (очень мягкие пороги)
        if score >= 75:
            print("✅ ВЫСОКАЯ ВЕРОЯТНОСТЬ: Это один и тот же человек!")
            print("   (Отличное совпадение)")
        elif score >= 55:
            print("✅ СОВПАДЕНИЕ: Скорее всего, один человек")
            print("   (Хорошее совпадение)")
        elif score >= 35:
            print("⚠️  ПОХОЖИ: Возможно похожие люди")
            print("   (Среднее совпадение)")
        elif score >= 20:
            print("❌ НЕ СОВПАДАЮТ: Вероятно, разные люди")
            print("   (Низкое совпадение)")
        else:
            print("❌ СОВСЕМ РАЗНЫЕ: Точно разные люди")
            print("   (Очень низкое совпадение)")
        
        print("\n💡 Как интерпретировать (очень мягкие настройки):")
        print("   85-100% = один человек с разных ракурсов")
        print("   75-85%  = один человек, разное освещение")
        print("   55-75%  = один человек, значительная разница в условиях")
        print("   35-55%  = похожие люди (родственники?)")
        print("   20-40%  = разные люди")
        print("   0-20%   = совсем разные люди")
        
    except ValueError as e:
        print(f"\n❌ Ошибка обработки: {e}")
        print("   Возможные причины:")
        print("   - На фото нет лиц")
        print("   - Лицо слишком маленькое или нечеткое")
        print("   - Фото повреждено")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
    
    print("\n" + "=" * 60)


def main():
    """Главная функция."""
    
    # Определяем пути к фото
    if len(sys.argv) >= 3:
        # Пути переданы как аргументы
        photo1 = sys.argv[1]
        photo2 = sys.argv[2]
    else:
        # Используем дефолтные имена
        photo1 = './test_face_samples/ya3.jpg'
        photo2 = './test_face_samples/ya2.jpg'
        
        # Подсказка пользователю
        if not os.path.exists(photo1) or not os.path.exists(photo2):
            print("💡 Подсказка:")
            print("   Положите два фото в папку проекта с именами:")
            print("   - photo1.jpg")
            print("   - photo2.jpg")
            print("\n   ИЛИ укажите пути:")
            print("   python test_face_match.py path/to/photo1.jpg path/to/photo2.jpg")
            print()
    
    # Запускаем тест
    test_face_recognition(photo1, photo2)


if __name__ == "__main__":
    main()
