function addParticipant() {
  const login = document.getElementById("p_login").value.trim();
  const name = document.getElementById("p_name").value.trim();
  const fileInput = document.getElementById("p_photo");

  if (!login) {
    alert("Нужен логин");
    return;
  }
  if (!fileInput.files.length) {
    alert("Нужна фотография");
    return;
  }

  const fd = new FormData();
  fd.append("login", login);
  fd.append("name", name);
  fd.append("photo", fileInput.files[0]);

  fetch("/admin/add_participant", { method: "POST", body: fd })
    .then(async (r) => {
      const text = await r.text();
      try {
        return JSON.parse(text);
      } catch {
        return { status: "error", msg: text };
      }
    })
    .then((d) => {
      if (d.status === "ok") {
        alert("Участник создан. Обнови страницу чтобы увидеть в списке.");
        document.getElementById("p_login").value = "";
        document.getElementById("p_name").value = "";
        fileInput.value = "";

        // сброс превью
        const img = document.getElementById("photo_preview");
        const hint = document.getElementById("photo_preview_hint");
        if (img && hint) {
          img.style.display = "none";
          hint.style.display = "block";
        }
      } else {
        if (d.code === "NO_FACE") {
          alert(
            "Ошибка: на фото не обнаружено лицо человека.\n\n" + (d.msg || ""),
          );
        } else {
          alert("Ошибка: " + (d.msg || "unknown"));
        }
      }
    });
}

function addEvent() {
  fetch("/admin/add_event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: document.getElementById("e_title").value }),
  })
    .then((r) => r.json())
    .then((d) => {
      if (d.status === "ok") {
        alert("Событие добавлено. Обнови страницу.");
        document.getElementById("e_title").value = "";
      } else {
        alert("Ошибка: " + (d.msg || "unknown"));
      }
    });
}

function loadAttendance() {
  fetch("/admin/get_attendance")
    .then((r) => r.json())
    .then((data) => {
      document.getElementById("log").innerText = JSON.stringify(data, null, 2);
    });
}

function exportAttendance() {
  const participantId = document.getElementById("export_participant_id").value;
  const eventId = document.getElementById("export_event_id").value;
  const dateFrom = document.getElementById("export_date_from").value;
  const dateTo = document.getElementById("export_date_to").value;

  const params = new URLSearchParams();
  if (participantId) params.append("participant_id", participantId);
  if (eventId) params.append("event_id", eventId);
  if (dateFrom) params.append("date_from", dateFrom);
  if (dateTo) params.append("date_to", dateTo);

  fetch(`/admin/export_attendance?${params.toString()}`)
    .then((r) => r.json())
    .then((data) => {
      if (data.status === "ok") {
        const resultDiv = document.getElementById("export_result");
        resultDiv.innerHTML = `
          <strong>✓ Экспорт выполнен успешно!</strong><br>
          Файл: <code>${data.filename}</code><br>
          Путь: <code>${data.path}</code><br>
          Записей: ${data.total_records}
        `;
      } else {
        alert("Ошибка экспорта: " + (data.msg || "unknown"));
      }
    })
    .catch((err) => {
      alert("Ошибка: " + err.message);
    });
}

const photoInput = document.getElementById("p_photo");
if (photoInput) {
  photoInput.addEventListener("change", () => {
    const file = photoInput.files && photoInput.files[0];
    const img = document.getElementById("photo_preview");
    const hint = document.getElementById("photo_preview_hint");

    if (!file) {
      img.style.display = "none";
      hint.style.display = "block";
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      img.src = e.target.result;
      img.style.display = "block";
      hint.style.display = "none";
    };
    reader.readAsDataURL(file);
  });
}
