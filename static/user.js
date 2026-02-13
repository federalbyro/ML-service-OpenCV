// Глобальные переменные
let currentMode = "file"; // 'file' или 'camera'
let videoStream = null;
let capturedBlob = null;

// Переключение режима (файл/камера)
function switchMode(mode) {
  currentMode = mode;

  const fileMode = document.getElementById("fileMode");
  const cameraMode = document.getElementById("cameraMode");
  const btnFile = document.getElementById("btnFileMode");
  const btnCamera = document.getElementById("btnCameraMode");

  if (mode === "file") {
    fileMode.style.display = "block";
    cameraMode.style.display = "none";
    btnFile.classList.add("active");
    btnCamera.classList.remove("active");
    stopCamera();
  } else {
    fileMode.style.display = "none";
    cameraMode.style.display = "block";
    btnFile.classList.remove("active");
    btnCamera.classList.add("active");
  }

  // Сброс результата
  document.getElementById("result").innerHTML = "";
  capturedBlob = null;
}

// Превью загруженного файла
document.getElementById("fileInput").addEventListener("change", (e) => {
  const file = e.target.files[0];
  const preview = document.getElementById("filePreview");
  const img = document.getElementById("filePreviewImg");

  if (file) {
    const url = URL.createObjectURL(file);
    img.src = url;
    preview.style.display = "block";
  } else {
    preview.style.display = "none";
  }
});

// Запуск камеры
async function startCamera() {
  try {
    videoStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: 640, height: 480 },
    });

    const video = document.getElementById("video");
    video.srcObject = videoStream;
    video.style.display = "block";

    document.getElementById("btnStartCamera").style.display = "none";
    document.getElementById("btnCapture").style.display = "inline-block";
    document.getElementById("capturedPreview").style.display = "none";
  } catch (err) {
    alert("Не удалось получить доступ к камере: " + err.message);
    console.error(err);
  }
}

// Остановка камеры
function stopCamera() {
  if (videoStream) {
    videoStream.getTracks().forEach((track) => track.stop());
    videoStream = null;
  }

  const video = document.getElementById("video");
  video.style.display = "none";
  video.srcObject = null;

  document.getElementById("btnStartCamera").style.display = "inline-block";
  document.getElementById("btnCapture").style.display = "none";
  document.getElementById("btnRetake").style.display = "none";
}

// Захват фото
function capturePhoto() {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");

  // Устанавливаем размеры canvas как у видео
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  // Рисуем текущий кадр на canvas
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  // Конвертируем в blob
  canvas.toBlob(
    (blob) => {
      capturedBlob = blob;

      // Показываем превью
      const url = URL.createObjectURL(blob);
      document.getElementById("capturedImg").src = url;
      document.getElementById("capturedPreview").style.display = "block";

      // Прячем видео и меняем кнопки
      video.style.display = "none";
      document.getElementById("btnCapture").style.display = "none";
      document.getElementById("btnRetake").style.display = "inline-block";

      // Останавливаем поток
      stopCamera();
    },
    "image/jpeg",
    0.9,
  );
}

// Переснять фото
function retakePhoto() {
  capturedBlob = null;
  document.getElementById("capturedPreview").style.display = "none";
  document.getElementById("btnRetake").style.display = "none";
  startCamera();
}

// Регистрация участника
async function register() {
  const eventId = document.getElementById("event_id").value;
  const name = document.getElementById("name").value.trim();
  const resultDiv = document.getElementById("result");

  // Валидация
  if (!eventId) {
    resultDiv.innerHTML = '<span class="error">❌ Выберите мероприятие</span>';
    return;
  }

  if (!name) {
    resultDiv.innerHTML = '<span class="error">❌ Введите ваше имя</span>';
    return;
  }

  // Получаем фото в зависимости от режима
  let photoBlob = null;

  if (currentMode === "file") {
    const fileInput = document.getElementById("fileInput");
    if (!fileInput.files || !fileInput.files[0]) {
      resultDiv.innerHTML =
        '<span class="error">❌ Выберите файл с фото</span>';
      return;
    }
    photoBlob = fileInput.files[0];
  } else {
    if (!capturedBlob) {
      resultDiv.innerHTML =
        '<span class="error">❌ Сделайте фото с камеры</span>';
      return;
    }
    photoBlob = capturedBlob;
  }

  // Отправка данных
  const formData = new FormData();
  formData.append("event_id", eventId);
  formData.append("name", name);
  formData.append("photo", photoBlob, "photo.jpg");

  resultDiv.innerHTML =
    '<span class="info">⏳ Идет проверка и регистрация...</span>';

  try {
    const response = await fetch("/register", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    // Обработка результата
    if (data.status === "registered") {
      resultDiv.innerHTML = `
        <span class="success">✅ Успешно зарегистрированы!</span><br>
        <strong>Логин:</strong> ${data.login}<br>
        <strong>Имя:</strong> ${data.name || "не указано"}<br>
        <strong>Совпадение:</strong> ${Math.round(data.score)}%
      `;
    } else if (data.status === "already_registered") {
      resultDiv.innerHTML = `
        <span class="warning">⚠️ Вы уже зарегистрированы на это мероприятие</span><br>
        <strong>Логин:</strong> ${data.login}<br>
        <strong>Совпадение:</strong> ${Math.round(data.score)}%
      `;
    } else if (data.status === "not_found") {
      const msg = data.best_candidate
        ? `Ближайший кандидат: ${data.best_candidate} (${Math.round(data.best_score)}%)`
        : "В базе нет участников";
      resultDiv.innerHTML = `
        <span class="error">❌ Вас нет в базе участников</span><br>
        ${msg}<br>
        <em>Обратитесь к администратору для добавления в систему</em>
      `;
    } else if (data.status === "bad_photo") {
      resultDiv.innerHTML = `
        <span class="error">❌ Фото не подходит</span><br>
        ${data.msg || "На фото должно быть ровно одно лицо"}
      `;
    } else {
      resultDiv.innerHTML = `
        <span class="error">❌ Ошибка: ${data.msg || "Неизвестная ошибка"}</span>
      `;
    }
  } catch (err) {
    resultDiv.innerHTML = `
      <span class="error">❌ Ошибка сети: ${err.message}</span>
    `;
  }
}
