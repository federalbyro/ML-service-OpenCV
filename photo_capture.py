import os
import cv2

# --- Windows short-path fix (для кириллицы в путях) ---
def _to_short_path(path: str) -> str:
    """Возвращает DOS 8.3 short path на Windows. На других ОС — как есть."""
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


# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASCADE_PATH = os.path.join(BASE_DIR, "cascades", "haarcascade_frontalface_default.xml")


def validate_face(
    photo_path: str,
    scaleFactor: float = 1.3,
    minNeighbors: int = 5,
    minSize=(30, 30),
    require_single_face: bool = True,
) -> bool:
    # 1) Проверка каскада
    if not os.path.isfile(CASCADE_PATH):
        raise RuntimeError(f"Не найден файл каскада: {CASCADE_PATH}")

    try:
        size = os.path.getsize(CASCADE_PATH)
    except OSError as e:
        raise RuntimeError(f"Не удалось получить размер файла каскада: {CASCADE_PATH}. {e}") from e

    if size < 1000:  # на всякий случай: xml должен быть существенно больше
        raise RuntimeError(f"Файл каскада подозрительно маленький ({size} байт): {CASCADE_PATH}")

    cascade_path_for_cv = _to_short_path(CASCADE_PATH)
    face_cascade = cv2.CascadeClassifier(cascade_path_for_cv)

    if face_cascade.empty():
        raise RuntimeError(f"Не удалось загрузить каскад: {cascade_path_for_cv}")

    # 2) Проверка входного фото
    if not os.path.isfile(photo_path):
        raise RuntimeError(f"Не найден файл изображения: {photo_path}")

    image = cv2.imread(photo_path)
    if image is None:
        raise RuntimeError("Не удалось прочитать изображение (cv2.imread вернул None)")

    # 3) Детект
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=scaleFactor,
        minNeighbors=minNeighbors,
        minSize=minSize,
    )

    return (len(faces) == 1) if require_single_face else (len(faces) > 0)
