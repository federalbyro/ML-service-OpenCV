function register() {
  fetch("/register", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      event_id: document.getElementById("event_id").value
    })
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
  });
}
