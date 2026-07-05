/**
 * Lenni borrower workspace — Land info / Loan info / My info tabs.
 */
(function () {
  var WS = { addrs: [], sel: null, seq: 1, profile: {}, tab: "land" };

  function money(n) {
    return "$" + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function kpis(rows) {
    return (
      '<div class="sess-kpis">' +
      rows
        .map(function (f) {
          return (
            '<div class="sess-kpi"><span class="tiny muted">' +
            f[0] +
            '</span><b style="font-size:14px">' +
            f[1] +
            "</b></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function acc(open, icon, title, pill, body) {
    return (
      '<div class="acc' +
      (open ? " open" : "") +
      '"><div class="acc-head" onclick="this.parentNode.classList.toggle(\'open\')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">' +
      icon +
      "</span> " +
      title +
      (pill ? " " + pill : "") +
      '</h3><span>▾</span></div><div class="acc-body">' +
      body +
      "</div></div>"
    );
  }

  function renderSide() {
    var el = document.getElementById("wsSide");
    if (!el) return;
    var html =
      '<div class="ws-side-head">ADDRESSES</div>' +
      WS.addrs
        .map(function (a) {
          var p = a.match.listing_profile;
          return (
            '<div class="ws-addr' +
            (WS.sel === a.id ? " on" : "") +
            '" onclick="LenniWS.select(' +
            a.id +
            ')"><b>' +
            (p.short || p.title) +
            '</b><span class="tiny muted">' +
            (p.property_type || "") +
            (p.price ? " · " + p.price : "") +
            '</span><span class="ws-x" onclick="event.stopPropagation();LenniWS.remove(' +
            a.id +
            ')">×</span></div>'
          );
        })
        .join("") ||
      '<p class="tiny muted" style="padding:6px 2px">No listings yet.</p>';
    el.innerHTML = html;
  }

  function landTab(a) {
    var p = a.match.listing_profile;
    var facts = (p.facts || []).map(function (f) {
      return '<div class="sess-kpi"><span class="tiny muted">' + f[0] + '</span><b style="font-size:14px">' + f[1] + "</b></div>";
    }).join("");
    return (
      '<div class="sess-panel"><h3 class="serif" style="font-size:20px">' +
      (p.property_type || "Property") +
      (p.price ? " · asking " + p.price : "") +
      '</h3><p class="muted" style="margin:12px 0">' +
      (p.summary || "") +
      '</p><div class="sess-kpis">' +
      facts +
      "</div></div>" +
      acc(true, "📍", "Listing profile", '<span class="pill live-badge">From your input</span>', "<p class=\"muted\">" + (p.raw_input || "").replace(/</g, "&lt;") + "</p>")
    );
  }

  function loanTab(a) {
    var prods = a.match.loan_products || [];
    var h =
      '<div class="sess-panel"><h3 class="serif" style="font-size:20px">Loan products that fit</h3><p class="tiny muted" style="margin:8px 0 16px">Pick the product that matches your plan.</p><div class="grid g3">' +
      prods
        .map(function (pr) {
          var on = a.loan === pr.subtype_slug;
          return (
            '<div class="card click lc' +
            (on ? " ws-loan-on" : "") +
            '" onclick="LenniWS.pickLoan(' +
            a.id +
            ",'" +
            pr.subtype_slug +
            "')\"><div class=\"lc-cat\">" +
            (pr.parent_name || "") +
            '</div><h3 class="serif" style="font-size:17px">' +
            pr.title +
            '</h3><p class="tiny muted">' +
            (pr.reason || "") +
            '</p><div class="lc-meta"><span class="muted">' +
            Math.round((pr.confidence || 0.5) * 100) +
            '% fit</span><span style="color:var(--accent-d);font-weight:700">' +
            (on ? "✓ Selected" : "Select →") +
            "</span></div></div>"
          );
        })
        .join("") +
      "</div></div>";

    if (!a.loan) {
      return (
        h +
        '<div class="sess-panel center" style="padding:28px"><p class="muted">Select a loan product to see banks and approach guidance.</p></div>'
      );
    }

    var sel = prods.find(function (x) { return x.subtype_slug === a.loan; }) || a.match.primary_product;
    var key = sel ? sel.parent_key : "mf";
    var banks = (a.match.recommended_banks || []).slice(0, 8);
    var max = (banks[0] && banks[0].portfolio_pct) || 1;

    h +=
      '<div class="sess-panel"><h3 class="serif" style="font-size:18px">Banks that do <em>' +
      (sel ? sel.title : "this loan") +
      "</em> near " +
      (a.match.listing_profile.metro || LOC) +
      '</h3><div class="rank" style="margin-top:14px">' +
      banks
        .map(function (b, i) {
          return (
            '<div class="rank-row" onclick="openBank(' +
            b.id +
            ')"><div class="pos">' +
            (i + 1) +
            '</div><div class="nm">' +
            b.name +
            (b.icp ? ' <span class="pill icp-badge">ICP</span>' : "") +
            "<small>" +
            b.city +
            " · " +
            assetStr(b.assets_m) +
            "</small></div><div class=\"rank-pct\"><div class=\"t\"><div class=\"f\" style=\"width:" +
            (b.portfolio_pct / max) * 100 +
            '%"></div></div><b>' +
            b.portfolio_pct +
            "%</b></div></div>"
          );
        })
        .join("") +
      "</div></div>";

    var road = a.match.roadmap || {};
    var approach = road.how_to_approach || {};
    if (approach.opening) {
      h += acc(true, "📞", "How to approach", "", '<p class="muted"><b>Opening:</b> ' + approach.opening + "</p>" +
        (approach.questions && approach.questions.length
          ? '<ul class="muted" style="margin-top:12px">' + approach.questions.map(function (q) { return "<li>" + q + "</li>"; }).join("") + "</ul>"
          : ""));
    }
    if (road.what_to_prepare && road.what_to_prepare.length) {
      h += acc(false, "📋", "What to prepare", "", '<ul class="muted">' + road.what_to_prepare.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul>");
    }
    if (road.steps) {
      h += acc(false, "🗓", "Roadmap", "", '<ol class="muted">' + road.steps.map(function (s) { return "<li><b>" + s.title + "</b> — " + s.detail + "</li>"; }).join("") + "</ol>");
    }
    return h;
  }

  function meTab() {
    return '<div class="sess-panel"><h3 class="serif">My info</h3><p class="tiny muted" style="margin-top:8px">Profile fields unlock sharper matching in production. Demo workspace — optional for now.</p></div>';
  }

  function renderMain() {
    var main = document.getElementById("wsMain");
    if (!main) return;
    var a = WS.addrs.find(function (x) { return x.id === WS.sel; });
    if (!a) {
      main.innerHTML =
        '<div class="sess-panel"><h3 class="serif">No address selected</h3><p class="muted" style="margin-top:8px">Paste a listing on the home page or in the sidebar — Lenni builds land info, loan info, and your package.</p></div>';
      return;
    }
    var tabs =
      '<div class="tabs"><div class="tab' +
      (WS.tab === "land" ? " active" : "") +
      '" onclick="LenniWS.setTab(\'land\')">Land info</div><div class="tab' +
      (WS.tab === "loan" ? " active" : "") +
      '" onclick="LenniWS.setTab(\'loan\')">Loan info</div><div class="tab' +
      (WS.tab === "me" ? " active" : "") +
      '" onclick="LenniWS.setTab(\'me\')">My info</div></div>';
    var body = WS.tab === "land" ? landTab(a) : WS.tab === "loan" ? loanTab(a) : meTab();
    main.innerHTML =
      '<p class="tiny muted" style="margin:4px 2px 12px">Engine: <b>' +
      (a.match.engine || "rules") +
      "</b> · " +
      (a.match.disclaimer || "") +
      "</p>" +
      tabs +
      body;
  }

  function renderWS() {
    renderSide();
    renderMain();
    var sid = document.getElementById("sId");
    if (sid) sid.textContent = "SESSION — " + (WS.seq - 1) + " listing" + (WS.addrs.length === 1 ? "" : "s");
  }

  function addFromMatch(text, match) {
    var a = {
      id: WS.seq++,
      text: text,
      match: match,
      loan: match.primary_product ? match.primary_product.subtype_slug : null,
    };
    WS.addrs.push(a);
    WS.sel = a.id;
    renderWS();
    go("session");
    toast("Listing read — workspace ready for " + (match.listing_profile.short || "your deal") + ".");
  }

  function startSession(text) {
    if (!text || !text.trim()) return;
    var loading = document.getElementById("wsMain");
    if (loading) loading.innerHTML = '<div class="sess-panel center"><p class="muted">Reading listing…</p></div>';
    go("session");
    LenniMatch.matchDeal(text.trim(), LOC).then(function (match) {
      addFromMatch(text, match);
    });
  }

  window.LenniWS = {
    startSession: startSession,
    add: function (text) {
      startSession(text);
    },
    select: function (id) {
      WS.sel = id;
      renderWS();
    },
    remove: function (id) {
      WS.addrs = WS.addrs.filter(function (x) { return x.id !== id; });
      if (WS.sel === id) WS.sel = WS.addrs.length ? WS.addrs[WS.addrs.length - 1].id : null;
      renderWS();
    },
    pickLoan: function (id, slug) {
      var a = WS.addrs.find(function (x) { return x.id === id; });
      if (!a) return;
      a.loan = a.loan === slug ? null : slug;
      renderWS();
    },
    setTab: function (t) {
      WS.tab = t;
      renderMain();
    },
  };

  window.heroAsk = function () {
    var el = document.getElementById("heroPaste");
    if (!el || !el.value.trim()) return;
    LenniWS.startSession(el.value);
    el.value = "";
  };

  window.wsAdd = function () {
    var el = document.getElementById("wsPaste");
    if (!el || !el.value.trim()) {
      toast("Paste a listing link or describe the property first.");
      return;
    }
    LenniWS.startSession(el.value);
    el.value = "";
  };
})();
