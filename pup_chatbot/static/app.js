const box = document.getElementById("messages");
const input = document.getElementById("q");
const sendBtn = document.getElementById("send");
let busy = false;

function add(role, text, meta) {
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.textContent = text;
  if (role === "bot" && meta) {
    const fb = document.createElement("div");
    fb.className = "fb";
    fb.innerHTML = "<span>Nakatulong ba?</span>";
    ["👍", "👎"].forEach((icon, i) => {
      const b = document.createElement("button");
      b.textContent = icon;
      b.onclick = () => {
        fetch("/api/feedback", {method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: meta.question, entry_id: meta.entry_id, helpful: i === 0})});
        fb.innerHTML = "<span>Salamat sa feedback! 🙏</span>";
      };
      fb.appendChild(b);
    });
    d.appendChild(fb);
  }
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  return d;
}

function typing() {
  const d = document.createElement("div");
  d.className = "msg bot typing";
  d.innerHTML = "<i></i><i></i><i></i>";
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  return d;
}

async function ask(text) {
  text = (text || input.value).trim();
  if (!text || busy) return;
  busy = true; sendBtn.disabled = true;
  input.value = "";
  add("user", text);
  const t = typing();
  try {
    const res = await fetch("/api/ask", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: text})});
    const data = await res.json();
    await new Promise(r => setTimeout(r, 350));
    t.remove();
    add("bot", data.answer, {question: text, entry_id: data.entry_id});
  } catch (e) {
    t.remove();
    add("bot", "Pasensya na po, may problema sa koneksyon. Pakisubukan ulit.");
  }
  busy = false; sendBtn.disabled = false; input.focus();
}

function askFromTopic(text) {
  document.getElementById("chat").scrollIntoView();
  ask(text);
}

function clearChat() {
  box.innerHTML = "";
  greet();
}

function greet() {
  if (box.childElementCount) return;
  add("bot", "Hello po! 👋 Ako ang FAQ Bot ng IT Department ng PUP Parañaque.\nMagtanong po tungkol sa enrollment, prerequisites, grading, o office schedules. Puwede po sa Tagalog, English, o Taglish!");
}

input.addEventListener("keydown", e => { if (e.key === "Enter") ask(); });
sendBtn.addEventListener("click", () => ask());
greet();
