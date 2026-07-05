/**
 * Lenni borrower chat client — conversational loan advisory UI.
 */
(function () {
  var API = window.LENNI_API_BASE || "";
  var sessionId = null;
  var messagesEl = document.getElementById("messages");
  var inputEl = document.getElementById("input");
  var sendBtn = document.getElementById("sendBtn");
  var resetBtn = document.getElementById("resetBtn");
  var typingEl = document.getElementById("typing");
  var slotsEl = document.getElementById("slots");
  var metaEl = document.getElementById("meta");
  var providerBadge = document.getElementById("providerBadge");

  function mdLite(text) {
    if (!text) return "";
    var html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/_(.+?)_/g, "<em>$1</em>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, function (m) {
      return "<ul>" + m + "</ul>";
    });
    html = html.replace(/\n\n/g, "<br><br>").replace(/\n/g, "<br>");
    return html;
  }

  function appendMessage(role, text) {
    var div = document.createElement("div");
    div.className = "msg " + (role === "user" ? "user" : "bot");
    if (role === "assistant" || role === "bot") {
      div.innerHTML = mdLite(text);
    } else {
      div.textContent = text;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderSlots(state) {
    if (!state) return;
    var slots = state.slots || {};
    var missing = state.missing_slots || [];
    var labels = {
      intent: "Plan",
      parent_key: "Type",
      city: "City",
      metro: "Metro",
      price_n: "Amount",
      units: "Units",
      acres: "Acres",
      occupancy_pct: "Occupancy",
      timeline: "Timeline",
      sponsor_experience: "Experience",
    };
    var typeLabels = {
      mf: "Multifamily", inv: "Investor CRE", own: "Owner-occupied",
      con: "Land / construction", ci: "C&I", res: "Residential", oth: "Ag / land",
    };
    var keys = ["intent", "parent_key", "city", "metro", "price_n", "units", "acres"];
    slotsEl.innerHTML = keys
      .map(function (k) {
        var val = slots[k];
        if (k === "parent_key" && val) val = typeLabels[val] || val;
        if (k === "price_n" && val) val = "$" + Number(val).toLocaleString();
        if (k === "intent" && val) val = String(val).replace(/_/g, " ");
        var isMiss = missing.indexOf(k) >= 0 && !val;
        return (
          "<li><span" +
          (isMiss ? ' class="missing"' : "") +
          ">" +
          (labels[k] || k) +
          '</span><span class="val">' +
          (val || (isMiss ? "—" : "")) +
          "</span></li>"
        );
      })
      .join("");
    metaEl.textContent =
      "Phase: " +
      (state.phase || "discover") +
      (state.ready_for_match ? " · Ready to match" : "") +
      (sessionId ? " · Session " + sessionId.slice(0, 8) + "…" : "");
  }

  function setLoading(on) {
    sendBtn.disabled = on;
    typingEl.hidden = !on;
  }

  function apiUrl(path) {
    return (API || "") + path;
  }

  function loadOpening() {
    fetch(apiUrl("/api/chat/opening"))
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        appendMessage("bot", data.reply || "Hi — tell me about your deal.");
        if (data.provider) providerBadge.textContent = data.provider;
      })
      .catch(function () {
        appendMessage(
          "bot",
          "Hi — I'm Lenni. Tell me about the property or business you're trying to finance."
        );
        providerBadge.textContent = "offline";
      });
  }

  function sendMessage(text, reset) {
    if (!text && !reset) return;
    if (text) appendMessage("user", text);
    setLoading(true);
    fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text || "start",
        session_id: sessionId,
        reset: !!reset,
      }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        sessionId = data.session_id;
        appendMessage("bot", data.reply);
        if (data.state) renderSlots(data.state);
        if (data.provider) providerBadge.textContent = data.provider;
        if (data.slot_provider && data.provider !== data.slot_provider) {
          providerBadge.textContent = data.provider + " / slots:" + data.slot_provider;
        }
      })
      .catch(function (err) {
        appendMessage("bot", "Sorry — couldn't reach the Lenni API. Is the server running on port 8000?");
        providerBadge.textContent = "error";
        console.error(err);
      })
      .finally(function () {
        setLoading(false);
        inputEl.value = "";
        inputEl.focus();
      });
  }

  sendBtn.addEventListener("click", function () {
    sendMessage(inputEl.value.trim(), false);
  });

  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputEl.value.trim(), false);
    }
  });

  resetBtn.addEventListener("click", function () {
    messagesEl.innerHTML = "";
    sessionId = null;
    loadOpening();
  });

  fetch(apiUrl("/health"))
    .then(function (r) {
      return r.json();
    })
    .then(function (h) {
      providerBadge.textContent = h.llm_provider || "ok";
    })
    .catch(function () {
      providerBadge.textContent = "local";
    });

  loadOpening();
})();
