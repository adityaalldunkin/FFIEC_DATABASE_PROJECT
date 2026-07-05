/**
 * Lenni deal match client — calls backend API with local keyword fallback.
 */
(function (global) {
  var API_BASE = global.LENNI_API_BASE || "http://127.0.0.1:8000";

  function localMatch(text, metro) {
    var q = (text || "").toLowerCase();
    var profile = {
      title: text.slice(0, 80),
      short: metro || "Texas",
      property_type: "Commercial",
      parent_key: "mf",
      price: "",
      price_n: 0,
      metro: metro || LOC,
      facts: [["Input", text.slice(0, 120)]],
      summary: "Matched locally — start the API server for full listing analysis.",
      intent: "acquire",
    };
    var key = "mf";
    if (/owner|operate|occupied/.test(q)) key = "own";
    else if (/construction|ground|build|land|lot|acre/.test(q)) key = "con";
    else if (/retail|office|industrial|strip|investor|cre/.test(q)) key = "inv";
    else if (/working capital|equipment|business|sba/.test(q)) key = "ci";
    else if (/farm|ag |ranch/.test(q)) key = "oth";
    else if (/home|1-4|residential/.test(q)) key = "res";
    profile.parent_key = key;
    var pname = (PRODUCTS.find(function (p) { return p.key === key; }) || PRODUCTS[0]).name;
    profile.property_type = pname;

    var subHit = null;
    PRODUCTS.forEach(function (p) {
      (p.subtypes || []).forEach(function (s) {
        (s.keywords || []).forEach(function (kw) {
          if (kw && q.indexOf(kw.toLowerCase()) > -1) subHit = { parent: p, subtype: s };
        });
      });
    });

    var products = [];
    if (subHit) {
      products.push({
        parent_key: subHit.parent.key,
        parent_slug: subHit.parent.slug,
        parent_name: subHit.parent.name,
        subtype_slug: subHit.subtype.slug,
        title: subHit.subtype.title,
        reason: "Keyword match from your description",
        confidence: 0.6,
        page_url: subHit.subtype.pageUrl,
        what_to_prepare: [],
        how_to_approach: {},
      });
    } else {
      var par = PRODUCTS.find(function (p) { return p.key === key; });
      if (par && par.subtypes && par.subtypes[0]) {
        products.push({
          parent_key: par.key,
          parent_slug: par.slug,
          parent_name: par.name,
          subtype_slug: par.subtypes[0].slug,
          title: par.subtypes[0].title,
          reason: "Best-fit category from your description",
          confidence: 0.5,
          page_url: par.subtypes[0].pageUrl,
        });
      }
    }

    var list = banksNear(metro || LOC)
      .slice()
      .sort(function (a, b) { return mixScore(b, key) - mixScore(a, key); })
      .slice(0, 8);
    if (list.length < 5) {
      list = BANKS.slice()
        .sort(function (a, b) { return mixScore(b, key) - mixScore(a, key); })
        .slice(0, 8);
    }
    var banks = list.map(function (b) {
      var pct = mixScore(b, key);
      return {
        id: b.id,
        name: b.name,
        city: b.city,
        metro: b.metro,
        assets_m: b.assets,
        portfolio_pct: pct,
        icp: b.icp,
        why: pct + "% of loan book in this category (FFIEC).",
        page_url: b.pageUrl,
        website: b.website,
      };
    });

    return {
      listing_profile: profile,
      loan_products: products,
      primary_product: products[0] || null,
      recommended_banks: banks,
      roadmap: {
        steps: [
          { step: 1, title: "Confirm loan type", detail: "Review the matched product guide." },
          { step: 2, title: "Prepare documents", detail: "Gather property facts and financials." },
          { step: 3, title: "Shortlist banks", detail: "Start with top FFIEC portfolio matches." },
          { step: 4, title: "First call", detail: "Lead with your plan, not a rate quote." },
        ],
        how_to_approach: { opening: "", questions: [] },
        what_to_prepare: [],
      },
      engine: "local-fallback",
      disclaimer: "Local keyword match — run Lenni API for full analysis.",
    };
  }

  function matchDeal(text, metro) {
    var url = API_BASE + "/api/match";
    var body = JSON.stringify({ text: text, metro: metro || LOC, use_llm: true });
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body,
    })
      .then(function (r) {
        if (!r.ok) throw new Error("API " + r.status);
        return r.json();
      })
      .catch(function () {
        return localMatch(text, metro);
      });
  }

  global.LenniMatch = { matchDeal: matchDeal, localMatch: localMatch, API_BASE: API_BASE };
})(typeof window !== "undefined" ? window : this);
