"""
Content blocks for Lenni Borrower Website Guide PDF.
Written in plain, human prose — loaded by build_borrower_website_guide.py
"""

from __future__ import annotations

# Each entry: (section_title, body_text)
# Placeholders {live}, {period}, {n_banks}, etc. filled at build time.


def all_sections(ctx: dict) -> list[tuple[str, str]]:
    L = ctx["live"]
    p = ctx

    sections: list[tuple[str, str]] = []

    sections.append(("A note before you start", f"""
This guide was written for anyone who needs to understand the Lenni Borrower website — whether you are a commercial borrower shopping for a bank, a Lenni teammate explaining the product, or a developer who needs to update and redeploy the site.

It walks through every section of the live website in plain English. Where it helps, we explain why we built something a certain way, not just what it does.

The site lives here:

  {L}

As of {p['build_date']}, it contains {p['n_urls']} pages, {p['n_banks']} bank profiles, and about {p['n_objects']} files on AWS. All loan portfolio numbers come from FFIEC Call Reports for the period ending {p['period']}.

If you only read one section besides the introduction, read Section 15 (step-by-step borrower workflows) or the deployment and infrastructure sections (hosting overview through current architecture vs production target) depending on your role.
"""))

    sections.append(("What problem does this website solve?", f"""
If you have ever tried to find a Texas bank for a commercial loan, you know the usual process: Google around, click through generic bank websites, call a 1-800 number, and hope the person on the other end actually lends on your deal type.

The problem is that bank websites tell you what they want you to hear. They rarely tell you what they actually hold on their balance sheet.

Every insured bank in America files a quarterly Call Report with the federal government. That filing includes a detailed breakdown of the bank's loan portfolio — how much is in apartments, warehouses, business lines of credit, farmland, credit cards, and so on. It is public data. Almost nobody outside banking uses it.

Lenni Borrower reads that data for {p['n_banks']} Texas banks and ranks them by portfolio concentration. If a bank has 18% of its loans in multifamily apartments, that is a strong signal they understand apartment deals. If they have 2%, they might still lend to you — but they are not a specialist.

The site does not replace a loan officer. It does not quote rates or approve loans. What it does is save you weeks of blind outreach by showing you where to start.
"""))

    sections.append(("Who should use this site?", """
BORROWERS (primary audience)
  Real estate investors looking at apartments, offices, warehouses, retail centers, or hotels.
  Business owners who need a working capital line, equipment loan, or acquisition financing.
  Farmers and ranch operators shopping for land or operating credit.
  Anyone who wants to walk into a first bank meeting prepared.

BROKERS AND ADVISORS
  Commercial mortgage brokers building a lender list for a specific deal type.
  CPAs and attorneys whose clients need bank introductions.

LENNI TEAM AND PARTNERS
  Sales team identifying community banks in the $500M–$2B sweet spot.
  CLOs evaluating whether a bank is a portfolio fit before a first call.

RESEARCHERS AND AI SYSTEMS
  The site publishes sitemap.xml, robots.txt, llms.txt, and JSON data files specifically so search engines and large language models can index and cite the content accurately.

WHO IT IS NOT FOR (today)
  Home buyers looking for a 30-year residential mortgage — the focus is commercial.
  People who want to submit a loan application through Lenni — you still contact the bank directly.
  Anyone expecting live interest rates — rates are negotiated bank by bank and are not in Call Reports.
"""))

    sections.append(("The data behind the site — explained without jargon", f"""
Three public data sources feed the website. You do not need to memorize regulatory codes to use the site, but understanding the sources helps you trust what you see.

SOURCE 1: FFIEC CALL REPORTS (the loan portfolio numbers)

Every quarter, Texas banks file a Call Report with the FFIEC Central Data Repository. Think of it as a standardized financial snapshot. The loan section breaks the portfolio into categories — multifamily, investor real estate, owner-occupied buildings, construction, business loans, consumer loans, and more.

The headline number is total loans (regulatory code RCON2122). Every percentage on the site is calculated as:

  Category balance ÷ Total loans = Portfolio %

We call a bank a "specialist" in a category when that percentage is 8% or higher. At 15% or above, we consider them a deep specialist. These thresholds are industry convention for portfolio analysis, not a Lenni invention.

Reporting period on the live site: {p['period']}

SOURCE 2: FDIC BANKFIND (institution and branch data)

The FDIC publishes institution records with headquarters addresses, website URLs, deposit totals, charter types, and whether the bank qualifies as a "community bank" under FDIC criteria. Branch location files add street addresses for thousands of Texas offices.

This matters because a bank might be headquartered in Dallas but have branches in Waco, Tyler, and Longview. Borrowers in those cities should not ignore a Dallas HQ bank if it has local branches.

SOURCE 3: BANK WEBSITE SCRAPING (contact enrichment)

For 255 banks, we also captured publicly available information from their websites — phone numbers, short about-text, links to commercial banking pages, and FAQ excerpts where available. This is labeled with a capture date and links back to the source page. We take short excerpts only; full content stays on the bank's site.

WHAT WE DO NOT HAVE
  Interest rates, LTV limits, credit score minimums, loan officer names, or online application status. Those require a direct conversation with the bank.
"""))

    sections.append(("Home page — your starting point", f"""
URL: {L}/index.html

The home page is a single interactive application embedded in one HTML file (about 1 MB). It loads instantly and works without a server — all bank data is embedded in the page.

WHAT YOU SEE WHEN YOU ARRIVE

A green banner at the top shows live stats: {p['n_banks']} Texas banks, reporting period {p['period']}, and {p['n_icp']} banks in the community-bank sweet spot ($500M–$2B assets).

Below that, quick links to Texas Market, Insights, Stories, Playbook, Glossary, and the machine-readable llms.txt file.

THE MAIN HEADLINE reads: "Find the bank that already lends like your deal." That is the whole point of the site.

"MATCH MY DEAL" SEARCH BAR
  This is the most important interactive feature. Paste listing text from Zillow, LoopNet, or Crexi — or just describe your deal in plain English:
  "40-unit apartment bridge in Dallas, $4M" or "working capital line for a SaaS company in Austin."

  The system parses your text, suggests loan product matches, ranks banks by portfolio fit, and opens a Borrower Workspace with preparation steps. See the dedicated "Match my deal" sections later in this guide for example searches, what gets matched, and current limitations.

NAVIGATION TABS
  Home — overview and hero search
  Loan Types — browse seven loan categories interactively
  Find Banks — filter all {p['n_banks']} banks by metro, size, and specialty
  AI Terminal — type questions in plain English (keyword-based routing today)

WHEN YOU CLICK A BANK in the interactive view, you are taken to the full static profile page. Those pages have more detail — branch tables, enrichment, SEO metadata — and are better for sharing a direct link with a colleague.
"""))

    # Loan types - one section per parent with human prose
    for parent in p.get("parents", []):
        subs = parent.get("subtypes") or []
        sub_list = "\n".join(
            f"  • {s.get('title', '')} — {s.get('one_liner', '')[:120]}"
            for s in subs
        )
        sections.append((f"Loan guide: {parent.get('name', '')}", f"""
URL: {L}/loan-types/{parent.get('slug', '')}.html

{parent.get('short', '')}

This category maps to specific lines on the bank's Call Report: {parent.get('lines', '')}

WHY THIS CATEGORY MATTERS
{parent.get('learn', '')[:600]}

SUB-GUIDES UNDER THIS CATEGORY ({len(subs)} pages)
Each sub-guide is written for a specific deal situation — not just the parent category. For example, under Investor CRE you will find separate guides for office buildings, retail strips, industrial warehouses, mixed-use properties, and NNN single-tenant deals. The underwriting story, document checklist, and opening script differ for each.

{sub_list}

WHAT EVERY SUB-GUIDE INCLUDES
  Who the loan is for (in plain English)
  How community banks typically underwrite it
  A checklist of documents to prepare before your first call
  An opening script and questions to ask the lender
  A live table of Texas banks ranked by portfolio % in this category
  FAQ and links to related sub-types

The bank tables are not hand-curated. They are generated from Call Report data every time the site is rebuilt, so the rankings always reflect the latest filing.
"""))

    sections.append(("Texas Market — the big picture", f"""
URL: {L}/market/texas-overview.html

Before you dive into individual banks, it helps to understand the landscape. The Texas Market section answers: "What kind of lending market am I walking into?"

TEXAS OVERVIEW ({p['n_banks']} banks, period {p['period']})
  Median bank assets: {p['med_assets']}
  Median gross loans: {p['med_loans']}
  Median loans-to-assets: {p['med_lta']}%
  Banks in ICP band ($500M–$2B): {p['n_icp']}
  Portfolio-style commercial lenders: {p['portfolio_style']}

Texas is genuinely a commercial-lending state. The typical bank puts about {p['med_lta']}% of its assets into loans, and most of that is real estate and business lending — not credit cards or home mortgages.

PRODUCT AVAILABILITY PAGE
  Shows how many of the {p['n_banks']} banks report a non-zero balance in each loan category. This tells you how many banks to put on your outreach list:
  • Wide pool (C&I, investor CRE): plan for 10–15 conversations
  • Narrow pool (multifamily deep specialists, construction): plan for 6–8 targeted calls

ASSET BANDS PAGE
  Banks cluster by size. A $3M deal is enormous for a $150M bank and modest for a $3B regional. The asset band guide helps you match deal size to bank size.

ICP BANK DIRECTORY (paginated)
  All {p['n_icp']} banks in the $500M–$2B range, ranked by loan portfolio, 20 per page. This is the single most useful list for mid-market commercial borrowers.
"""))

    # Insights - expanded
    slug_map = {
        "I-01": "i-01-product-choice-breadth", "I-02": "i-02-market-structure",
        "I-03": "i-03-deal-size-fit", "I-04": "i-04-specialist-targeting",
        "I-05": "i-05-bank-size-fit", "I-06": "i-06-icp-opportunity",
        "I-07": "i-07-geography", "I-08": "i-08-market-momentum",
        "I-09": "i-09-lender-diligence", "I-10": "i-10-bank-archetypes",
        "I-11": "i-11-cross-sell", "I-12": "i-12-outreach-planning",
    }
    for ins in p.get("insights", []):
        slug = slug_map.get(ins.get("code", ""), "index")
        sections.append((f"Insight {ins.get('code', '')}: {ins.get('theme', '')}", f"""
URL: {L}/insights/{slug}.html

{ins.get('summary', '')}

WHY WE DOCUMENTED THIS
This insight comes from exploratory data analysis of all {p['n_banks']} Texas banks in the latest Call Report panel. We ran statistical tests — concentration indexes, percentile distributions, co-occurrence matrices — and translated the findings into something a borrower can act on.

WHAT TO DO
{ins.get('borrower_action', '')}

These insight pages are linked from scenario stories and the Borrower Playbook. They are also exported in data/market_insights.json for AI integrations.
"""))

    # Scenarios - one per scenario with narrative
    for sc in p.get("scenarios", []):
        actions = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(sc.get("action_plan", [])))
        questions = "\n".join(f"  • {q}" for q in sc.get("questions_to_ask", []))
        data_pts = "\n".join(f"  • {d}" for d in sc.get("data_points", []))
        sections.append((f"Borrower story: {sc.get('title', '')}", f"""
URL: {L}/scenarios/{sc.get('slug', '')}.html

THE DEAL
{sc.get('summary', '')}

Persona: {sc.get('persona', '')}
Location: {sc.get('location', '')}, Texas
Size: {sc.get('deal_size', '')}

THE SITUATION
{sc.get('situation', '')}

WHAT THE DATA TELLS YOU
{data_pts}

YOUR ACTION PLAN
{actions}

QUESTIONS FOR YOUR FIRST BANK CALL
{questions}

These stories are educational examples, not financial advice. They show how a prepared borrower uses Call Report data to build a shortlist, prepare documents, and ask smart questions — before anyone asks for your social security number.
"""))

    sections.append(("Bank profile pages — reading one like a borrower", f"""
URL pattern: {L}/banks/{{bank-id}}-{{bank-name}}.html
Count: {p['n_banks']} profiles

Example: {L}/banks/682563-frost-bank.html (Frost Bank, San Antonio — one of the largest Texas portfolios)

Every bank with complete Call Report data gets its own page. Here is how to read one in two minutes.

STEP 1: GLANCE AT THE BADGES
  "ICP ($500M–$2B)" means the bank is in Lenni's core community-bank segment — large enough for meaningful commercial deals, small enough to value relationships.
  "FDIC community bank" means the FDIC classifies it as a community institution.

STEP 2: LOOK AT THE PORTFOLIO MIX CHART
  This is the reason the site exists. Eleven categories show where the bank actually lends. A bar at 25% for Investor CRE means one quarter of their loan book is income-producing property. A bar at 3% for Multifamily means apartments are a side line, not a focus.

STEP 3: CHECK "GOOD FIT IF YOU NEED…"
  Auto-generated bullets based on specialties at 15%+ concentration.

STEP 4: SCROLL TO BRANCHES
  {p['n_banks']} banks, thousands of branches statewide. HQ city is not the whole story.

STEP 5: USE ENRICHMENT (when available)
  255 banks have phone numbers and commercial banking links scraped from their websites. Call the commercial lending line, not the retail 1-800 number.

STEP 6: CLICK THROUGH TO THEIR WEBSITE
  The site is a research tool. The relationship starts at the bank.
"""))

    sections.append(("City pages — finding banks near you", """
URL pattern: /cities/{city-name}.html — 40 cities covered

We built city pages for the 40 Texas cities with the most bank headquarters — Dallas, Houston, Austin, San Antonio, Fort Worth, El Paso, Waco, Tyler, Amarillo, and others.

Each page shows:
  How many banks are headquartered in the city
  How many banks have at least one branch there
  How many fall in the ICP ($500M–$2B) range
  A ranked table of the top 25 HQ banks by loan portfolio size

A practical tip: if your city only has two small HQ banks, expand your search. Many Texas community banks lend statewide from a single HQ. Check branch lists on bank profiles, and browse the ICP directory for banks that operate in your county even if they are based elsewhere.
"""))

    sections.append(("Guides — the reference shelf", f"""
URL: {L}/guides/

BORROWER PLAYBOOK
  Nine steps from "I need a loan" to "I have three term sheets." Start here if you are new to commercial bank shopping.

OUTREACH CHECKLIST
  Twelve checkboxes — printable — covering product definition, shortlist building, document prep, and parallel conversations.

GLOSSARY
  Plain-English definitions for Call Report terms. If you see "RCON1460" on a bank page and wonder what it means, the glossary explains it. Sourced from the Federal Reserve MDRM dictionary.

FAQ
  Eight common questions: data sources, what a Call Report is, whether rates are shown, whether you can apply on the site.

METHODOLOGY
  Technical documentation for researchers: join logic between FFIEC and FDIC, specialist threshold definition, known limitations.
"""))

    sections.append(("Match my deal — overview", f"""
The green "Match my deal" bar on the home page is the fastest way to go from "I have a deal" to "here are the banks that already lend like this."

In one sentence: you paste or describe your deal, and Lenni figures out the loan type, ranks {p['n_banks']} real Texas banks from public FFIEC Call Report data, and opens a workspace with a preparation roadmap.

THE SIMPLE FLOW

  Your text
    → Listing profile (what you are buying, where, and why)
    → Loan product matches (from our 27 sub-type guides)
    → Recommended banks (ranked by portfolio concentration)
    → Four-step prep roadmap (documents to gather + first-call script)

This is research and preparation — not a loan application, not a rate quote, and not an approval decision. Every bank name comes from real regulatory filings. Lenni never invents a bank.

This feature was built June 22, 2026. The sections that follow explain exactly what to type, what comes back, and what the system cannot do yet.
"""))

    sections.append(("Match my deal — what you can paste or type", """
You can use the search bar three ways:

1. PASTE LISTING TEXT (recommended)
   Copy the property description from Zillow, LoopNet, Crexi, or any listing page. Paste it into the bar. Include price, city, property type, and size (units, square feet, or acres) if the listing shows them.

2. PASTE A LISTING URL (with an important caveat)
   The search box shows Zillow, LoopNet, and Crexi as examples. Today, the system reads the TEXT you provide — it does not automatically fetch or scrape listing pages from those sites yet. If you paste only a URL, also paste the listing description below it, or write your own short summary.

3. DESCRIBE YOUR DEAL IN PLAIN ENGLISH
   No listing required. A single sentence works if it includes:
     • What it is (apartment, warehouse, land, restaurant, etc.)
     • Where (any Texas city or metro)
     • Size (40-unit, 120,000 SF, 12 acres)
     • Price ($4M, $849k)
     • What you want to do (buy, refinance, bridge, build, hold land, owner-occupy, working capital)

WORDS THAT HELP THE MATCHER

  Property type — apartment, warehouse, retail strip, office, hotel, land, farm, restaurant, manufacturing
  Size — "40-unit", "120,000 SF", "12.4 acres"
  Price — "$4M", "$849k", "asking $2.4 million"
  Intent — bridge, refinance, acquisition, ground-up construction, hold land, owner-occupied, working capital line
  Location — Dallas, Houston, Austin, Brenham, Midland, El Paso, and any other Texas city
"""))

    sections.append(("Match my deal — example searches", """
Below are real examples you can copy into "Match my deal" to see how the system responds. Each row shows what you might type and what Lenni typically matches it to.

MULTIFAMILY (APARTMENTS, 5+ UNITS)
  Type: "40-unit apartment value-add bridge loan in Fort Worth $4.2M"
  Matches: Multifamily → bridge or value-add/rehab

  Type: "48-unit garden-style apartment in Dallas, $4.2M bridge"
  Matches: Multifamily → bridge

INVESTOR CRE (RENTAL INCOME PROPERTY)
  Type: "120,000 SF warehouse refinance in Houston, $8.5M"
  Matches: Investor CRE → industrial

  Type: "12-unit retail strip refinance in El Paso, $2.4M"
  Matches: Investor CRE → retail

  Type: "95-room beachfront hotel refinance in Corpus Christi, $11M"
  Matches: Investor CRE → mixed-use

OWNER-OCCUPIED CRE (YOU OPERATE OUT OF THE BUILDING)
  Type: "Manufacturer buying 45,000 SF headquarters in Waco, $3.1M"
  Matches: Owner-occupied CRE → purchase

  Type: "6-physician orthopedic group buying 28,000 SF clinic in Tyler, $4.6M"
  Matches: Owner-occupied CRE → purchase

LAND & CONSTRUCTION
  Type: "12.4 acre land lot near Brenham TX asking $849,000 — holding for investment"
  Matches: Commercial construction → lot loans or land development

  Type: "Ground-up spec industrial in Midland, $5.5M construction loan"
  Matches: Commercial construction → ground-up

C&I / BUSINESS LENDING
  Type: "Working capital line of credit for manufacturing business in Houston"
  Matches: C&I / Business → working capital line

  Type: "$2M revolving line for Austin SaaS company"
  Matches: C&I / Business → working capital line

  Type: "Restaurant acquisition in San Antonio, $1.8M"
  Matches: C&I / Business → acquisition finance

  Type: "West Texas contractor financing $1.2M equipment fleet"
  Matches: C&I / Business → equipment

AGRICULTURE
  Type: "1,200 acres irrigated farmland near Amarillo, $6.8M"
  Matches: Ag & farmland → farmland purchase

Each example above corresponds to one of the 12 borrower scenario stories on the site (/scenarios/). Those pages add a fuller narrative, an action plan, and specific questions to ask lenders.
"""))

    sections.append(("Match my deal — what gets matched to your deal", f"""
When you click "Match my deal →", the system returns four things. Here is what each one means in plain English.

1. LISTING PROFILE
   A structured summary of what Lenni understood from your text:
     • Property type (Multifamily, Investor CRE, C&I, Land, etc.)
     • City and Texas metro area
     • Price, unit count, or acreage (when mentioned)
     • Intent — acquire, bridge, refinance, build, hold land, or owner-occupy
     • A short title like "40-unit · Dallas, TX · $4,000,000"

2. LOAN PRODUCT MATCHES
   One to three loan sub-types from our guide library (defined in content/loan_products.yaml). Each match includes:
     • The sub-type name (e.g. "Apartment bridge loan")
     • A confidence score based on keyword and intent rules
     • A link to the full sub-type guide page
     • "How to approach" — an opening script and questions to ask the lender

3. RECOMMENDED BANKS
   Up to ten Texas banks ranked by how much of their loan portfolio sits in the matched category. For each bank you see:
     • Bank name and RSSD ID (stable federal identifier)
     • Portfolio percentage in that category (from FFIEC Call Reports)
     • A one-line explanation ("12% of loan book in multifamily — active in this category per FFIEC filings")
     • A link to the bank's full profile page

   All {p['n_banks']} banks come from banks.json — real institutions, never invented names.

4. PREPARATION ROADMAP
   A four-step checklist built from the matched sub-type guide:
     • Step 1 — Understand your deal type
     • Step 2 — Gather documents (rent roll, financials, purchase contract, etc.)
     • Step 3 — Shortlist banks from the recommendations
     • Step 4 — First-call script and questions

The workspace then opens with three tabs: Land info (for land/development deals), Loan info (products + banks), and My info (borrower details — placeholder for future features).
"""))

    # Loan taxonomy for matcher — compact list from YAML
    tax_lines = []
    for parent in p.get("parents", []):
        subs = parent.get("subtypes") or []
        sub_names = ", ".join(s.get("title", "") for s in subs)
        tax_lines.append(f"  {parent.get('name', '')} ({len(subs)} sub-types)\n    {sub_names}")
    tax_block = "\n\n".join(tax_lines) if tax_lines else "  (See loan_products.yaml)"

    sections.append(("Match my deal — loan categories the matcher knows", f"""
The matcher maps your deal to one of seven parent loan categories and then to a specific sub-type within that category. There are 27 sub-types in total — the same guides you can browse under Loan Types on the site.

{tax_block}

HOW MATCHING WORKS (WITHOUT JARGON)

  Lenni scans your text for property-type words (apartment, warehouse, land, etc.) and intent words (bridge, refinance, build, hold). It scores each sub-type's keywords from the YAML guide library and picks the best fits. It then looks up which Texas banks report the highest portfolio share in that category on their Call Report.

Example: "40-unit bridge in Dallas" hits multifamily keywords + bridge intent → Apartment bridge loan → banks ranked by multifamily % (RCON1460 on the Call Report).
"""))

    sections.append(("Match my deal — what it does NOT do", """
Being clear about limits helps you use the tool correctly.

DOES NOT SCRAPE LISTING SITES (YET)
  Pasting a Zillow or LoopNet URL alone will not pull the listing automatically. Paste the description text or write your own summary.

DOES NOT QUOTE RATES OR TERMS
  FFIEC data shows portfolio composition, not pricing. Every bank sets its own rates and credit policy.

DOES NOT PREDICT APPROVAL
  A high portfolio share means the bank actively lends in that category — not that your specific deal will be approved.

DOES NOT LET YOU APPLY ON THE SITE
  There are no login forms, SSN fields, or application uploads. The site prepares you for conversations with real lenders.

DOES NOT REPLACE A LOAN OFFICER
  Use Lenni to build a shortlist and walk in prepared. The bank still underwrites your specific deal.

COUNTY / PARCEL RECORDS
  The Land info tab shows placeholders for public records. Production would connect to county APIs — not live today.

BORROWER PROFILE SAVES
  The My info tab is a UI stub. Your details are not saved between sessions yet.
"""))

    sections.append(("Match my deal — running the full engine locally", """
TWO MODES: FULL API vs BROWSER FALLBACK

On the live S3 site, "Match my deal" uses a browser-based keyword fallback when the Python API is not running. That fallback still ranks real banks from embedded data — it never makes up bank names.

For the full matching engine (same logic as production will use), run the API on your laptop:

TERMINAL 1 — Start the API
  cd ONLY_TEXAS_SINCE_2025
  source ../.venv/bin/activate
  python run_match_api.py
  → Listens at http://127.0.0.1:8000

TERMINAL 2 — Serve the static site
  cd borrower_site
  python -m http.server 8080
  → Open http://localhost:8080

OPTIONAL — OpenAI enrichment
  Set OPENAI_API_KEY in .env for smarter text extraction. Without it, keyword rules still work.

QUICK API TEST (no browser needed)
  curl -X POST http://127.0.0.1:8000/api/match \\
    -H 'Content-Type: application/json' \\
    -d '{{"text":"12.4 acre land near Brenham TX $849k hold","use_llm":false}}'

PRODUCTION STATUS
  The API runs locally today. Hosting it on AWS (Lambda + API Gateway or similar) and pointing the live site at it via window.LENNI_API_BASE is the recommended next step. Until then, the live site uses the browser fallback.
"""))

    sections.append(("SEO, search engines, and AI discoverability", f"""
We built the site to be found — by Google, by Bing, and by AI assistants that index llms.txt.

SITEMAP.XML — {p['n_urls']} URLs
  Every bank profile, loan guide, insight, scenario, city page, and market page. Submitted automatically to crawlers via robots.txt.

ROBOTS.TXT
  Allows all crawlers. Points to the sitemap.

LLMS.TXT and LLMS-FULL.TXT
  Machine-readable indexes designed for LLM crawlers (the llms.txt convention). The full version lists all {p['n_banks']} bank profile URLs.

JSON DATA FEEDS (data/ folder)
  banks.json — complete bank records for integrations
  loan_products.json — full taxonomy
  glossary.json — term definitions
  market_insights.json — stats and insight summaries

PER-PAGE SEO
  Unique title and meta description on every page.
  Canonical URLs pointing to the S3 website endpoint.
  Open Graph tags for social sharing.
  JSON-LD structured data (BankOrCreditUnion on profiles, Article on guides).

INTERNAL LINKING
  Scenario stories link to insights. Insights link to the playbook. Bank profiles link to loan type pages. The site is designed as a web of related content, not isolated pages.
"""))

    # DEPLOYMENT - comprehensive section split across multiple parts
    sections.append(("How the website is hosted — overview", f"""
The Lenni Borrower site is a static website — plain HTML, CSS, and JavaScript files with no server-side code running in production. That choice was deliberate: it is fast, cheap, secure (no database to hack), and easy for search engines to crawl.

HOSTING PROVIDER: Amazon Web Services (AWS) S3 Static Website Hosting
LIVE URL: {L}
BUCKET NAME: lenni-borrower
AWS REGION: us-east-2 (US East — Ohio)
AWS ACCOUNT ID: 629603795749

HOW THE SITE GETS TO PRODUCTION TODAY
  1. Run build_borrower_site.py locally → generates HTML/CSS/JS in borrower_site/
  2. Run aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
  3. Visitors open the S3 website endpoint directly — no CDN, no custom domain, no HTTPS

WHAT IS NOT CONFIGURED YET (important to know)
  • CloudFront (CDN) — not set up; no HTTPS on the live URL
  • ACM SSL certificate — not issued for this site
  • Route 53 custom DNS — lenni.io DNS exists in AWS but the borrower site does not use a custom domain like borrower.lenni.io yet
  • CI/CD pipeline — deploys are manual via AWS CLI
  • Production API — deal matcher runs locally only

The site is accessed directly via the S3 website endpoint over HTTP. Browsers show a "Not secure" label — that is expected and acceptable for a read-only demo site with no login forms. For public marketing long-term, CloudFront + HTTPS is the recommended next step.

The sections immediately following this one explain each "not configured" item in detail — what it means, why it matters, and what a production upgrade would look like.
"""))

    sections.append(("HTTP, HTTPS, and the Not secure browser warning", f"""
S3 static website hosting serves pages over HTTP only. There is no built-in TLS/SSL on the S3 website endpoint. That single limitation drives most of the other "not configured yet" items in this guide.

HTTP vs HTTPS — what is the difference?

  HTTP  — Unencrypted web traffic. URL starts with http://. Browsers may show "Not secure" in the address bar.
  HTTPS — Encrypted web traffic (TLS). URL starts with https://. Browsers show a padlock when the certificate is valid.

  With HTTP, anyone on the same network could see which pages you load (a privacy concern, not a data breach on our site).
  With HTTPS, content is encrypted between the browser and the server. Users and search engines expect it for public marketing sites.

WHY CHROME SHOWS "NOT SECURE" ON {L}

  You are using the S3 website endpoint over plain HTTP. The browser is correctly warning that traffic is not encrypted. This is not a bug — it is how S3 website hosting works without CloudFront in front.

WHY THIS IS ACCEPTABLE FOR THE DEMO TODAY

  The borrower site is read-only. There are no login forms, no passwords, no payment fields, and nowhere to enter sensitive personal data. Visitors only download public HTML, CSS, JavaScript, and JSON files. The main risk of HTTP here is privacy (someone could see what pages you browse) or, in theory, page tampering in transit — both low priority for a static research demo.

WHEN YOU NEED HTTPS

  For long-term public marketing under the lenni.io brand, HTTPS is standard. It removes the "Not secure" warning, enables a friendly URL like borrower.lenni.io, and is a prerequisite for treating the site as production-grade. The fix is CloudFront in front of S3 plus an ACM certificate — not a change to the S3 bucket itself.
"""))

    sections.append(("CloudFront (CDN) — what it is and why we have not set it up", f"""
WHAT CLOUDFRONT IS

  Amazon CloudFront is AWS's Content Delivery Network (CDN). Instead of every visitor fetching files directly from the lenni-borrower bucket in Ohio (us-east-2), CloudFront:

    • Caches copies of your files at edge locations worldwide (Dallas, London, Tokyo, etc.)
    • Serves requests from the nearest edge — faster for visitors far from Ohio
    • Sits in front of S3 as the public entry point to the website
    • Can terminate HTTPS using an SSL certificate — which S3 website hosting alone cannot do

WHAT "NOT SET UP" MEANS FOR THIS PROJECT

  There is no CloudFront distribution pointing at lenni-borrower.s3-website.us-east-2.amazonaws.com. Users go straight to S3. Consequences:

    • No CDN edge caching or global performance boost
    • No HTTPS termination layer
    • No place to attach a custom domain name (that is almost always done on CloudFront, not on S3 directly)

TYPICAL ARCHITECTURE ONCE CLOUDFRONT EXISTS

  Browser → HTTPS → CloudFront (edge caches worldwide) → HTTP fetch → S3 website endpoint

  CloudFront talks to S3 on the backend; visitors only see CloudFront. You configure the origin as the S3 website endpoint (lenni-borrower.s3-website.us-east-2.amazonaws.com), not the REST API endpoint (lenni-borrower.s3.amazonaws.com) — they behave differently.

SETTINGS TO USE WHEN YOU BUILD IT

  Origin: lenni-borrower.s3-website.us-east-2.amazonaws.com
  Viewer protocol policy: Redirect HTTP to HTTPS
  Alternate domain name (CNAME): borrower.lenni.io (after DNS and certificate are ready)
  SSL certificate: from ACM in us-east-1 (required for CloudFront even though the bucket is in us-east-2)
"""))

    sections.append(("ACM SSL certificates — what they are and why none is issued yet", """
WHAT ACM IS

  AWS Certificate Manager (ACM) provides free SSL/TLS certificates for use on AWS services — especially CloudFront and load balancers. A certificate proves to browsers that a hostname (for example borrower.lenni.io) really belongs to you and enables the padlock in the address bar.

WHAT A CERTIFICATE DOES

  When a visitor opens https://borrower.lenni.io, the browser checks the certificate. If it is valid and matches the domain, the connection is encrypted and the padlock appears. Without a certificate, HTTPS cannot work on that hostname.

WHY NO CERTIFICATE IS ISSUED FOR THE BORROWER SITE YET

  Certificates are requested for specific hostnames. Today the site is accessed via the auto-generated S3 hostname (lenni-borrower.s3-website.us-east-2.amazonaws.com). You could theoretically certificate that name, but the normal path is:

    1. Choose a branded subdomain (borrower.lenni.io or similar)
    2. Request a certificate in ACM for that subdomain
    3. Prove domain ownership (DNS validation via Route 53 is easiest since lenni.io already uses Route 53)
    4. Attach the certificate to a CloudFront distribution

IMPORTANT AWS DETAIL

  CloudFront requires certificates to be in us-east-1 (N. Virginia), even when your S3 bucket lives in us-east-2 (Ohio). This confuses many first-time setups — request the cert in the right region before attaching it to CloudFront.

UNTIL THAT CHAIN EXISTS

  There is no SSL for the borrower site. The live URL stays HTTP-only on the S3 endpoint. That is expected for the current minimal demo setup.
"""))

    sections.append(("Route 53 custom DNS — lenni.io exists but the borrower site does not use it", """
WHAT ROUTE 53 IS

  Amazon Route 53 is AWS's DNS (Domain Name System) service. DNS translates human-readable names like borrower.lenni.io into addresses and AWS resources that browsers can reach.

WHAT YOU HAVE TODAY

  The lenni.io domain's nameservers point to Route 53 in AWS (not GoDaddy's DNS panel for record edits). DNS for the Lenni brand is already managed in AWS.

WHAT YOU DO NOT HAVE YET

  A DNS record that sends a subdomain like borrower.lenni.io to the borrower website. Visitors must use the long S3 URL:

    http://lenni-borrower.s3-website.us-east-2.amazonaws.com

  That works, but it is not branded, is hard to share, and cannot use HTTPS without CloudFront in the middle.

WHAT "WIRED UP" WOULD LOOK LIKE

  1. Request an ACM certificate for borrower.lenni.io (validated via Route 53)
  2. Create a CloudFront distribution with alternate domain name (CNAME) = borrower.lenni.io
  3. Create a Route 53 A record (Alias) pointing borrower.lenni.io to the CloudFront distribution

  Then https://borrower.lenni.io becomes the friendly, branded URL.

WHY DNS IS SEPARATE FROM S3

  S3 bucket names are globally unique and auto-generated for website endpoints. Custom domains almost always go through CloudFront plus Route 53, not by pointing DNS directly at the raw bucket hostname. The same pattern was discussed for Convey app hosting (convey.lenni.io) but has not been applied to the borrower S3 site yet.
"""))

    sections.append(("CI/CD pipeline vs manual AWS CLI deploys", """
WHAT CI/CD MEANS

  Continuous Integration / Continuous Deployment — automation that builds and deploys the site when you push code (for example a GitHub Action on every merge to main), without a human running commands on a laptop.

WHAT WE DO TODAY (MANUAL)

  Every production update requires a developer to run two commands on a Mac:

    python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
    aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete

  Credentials come from IAM user aditya-cli, scoped by the LenniBorrowerS3Deploy policy (ListBucket, GetObject, PutObject, DeleteObject on lenni-borrower only).

MANUAL DEPLOY — TRADEOFFS

  Pros: Simple, full control, no pipeline to maintain, fine for infrequent content updates.
  Cons: Depends on one machine and local AWS config; easy to forget a step; no automatic deploy on git push.

CI/CD — WHAT "NOT CONFIGURED" MEANS

  No GitHub Action (or similar) runs build_borrower_site.py and aws s3 sync automatically. Proposed future setup:

    GitHub push to main → GitHub Actions runner → build → aws s3 sync
    Requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY stored as GitHub repository secrets.

  Not implemented as of June 2026. Every production update is a deliberate manual run.
"""))

    sections.append(("Production API — why the deal matcher runs locally only", f"""
TWO DIFFERENT PIECES IN THE STACK

  Borrower static site — HTML, CSS, JavaScript. Bank profiles, guides, workspace UI. Hosted on S3 (public, Ohio). URL: {L}

  Deal matcher API — Python FastAPI backend (api/main.py, run_match_api.py). Ranks banks, builds preparation roadmaps from deal text. Runs on your laptop today — typically http://127.0.0.1:8000

HOW THE WORKSPACE USES THE API

  The home page "Match my deal" feature calls an API base URL (window.LENNI_API_BASE in the built site). When the API is running locally, full matching works. When it is not, the live S3 site falls back to browser-based keyword matching — still grounded in real bank data from banks.json, never hallucinated bank names.

WHAT "RUNS LOCALLY ONLY" MEANS FOR PUBLIC VISITORS

  Anyone on the internet who opens only the S3 URL gets the static site. They do not get a hosted match API unless you deploy FastAPI to AWS (options documented: Lambda + API Gateway, or a small EC2/ECS service) and set LENNI_API_BASE in the built HTML to that production URL.

  CORS in api/main.py already includes the S3 website origin — the backend is ready to accept requests from the static site; it simply is not deployed to a public endpoint yet.

PRODUCTION UPGRADE STEPS (SUMMARY)

  1. Deploy api/main.py to Lambda + API Gateway, or EC2/ECS
  2. Set window.LENNI_API_BASE in index.html (via build_borrower_website.py) to the production API URL
  3. Rebuild and aws s3 sync
  4. Optionally put the API behind its own subdomain (api.lenni.io) with HTTPS via CloudFront or API Gateway
"""))

    sections.append(("Current architecture vs production target", f"""
CURRENT SETUP (MINIMAL DEMO — WHAT EXISTS TODAY)

  Developer machine
    → build_borrower_site.py → borrower_site/
    → aws s3 sync → S3 bucket lenni-borrower (us-east-2)

  Visitor
    → HTTP → {L}
    (direct S3 website endpoint, no CDN, no custom domain, no encryption)

  Deal matcher API
    → localhost:8000 only (not reachable by public internet visitors)

PRODUCTION TARGET (NOT BUILT YET)

  Visitor
    → HTTPS → borrower.lenni.io
    → CloudFront (CDN + ACM certificate)
    → S3 website origin

  Visitor using "Match my deal"
    → HTTPS → api.lenni.io (or similar)
    → API Gateway / Lambda / ECS
    → match_deal logic

  Developer
    → git push to main
    → GitHub Actions → build + aws s3 sync (CI/CD)

WHY CLOUDFRONT + HTTPS IS THE RECOMMENDED NEXT STEP FOR THE STATIC SITE

  For the read-only demo, HTTP on S3 is a reasonable shortcut — cheap and few moving parts.

  For public marketing long-term, CloudFront + HTTPS provides:

    • Trust — padlock, no "Not secure" warning
    • Brand — borrower.lenni.io instead of an AWS hostname
    • Performance — CDN edge caching worldwide
    • SEO and sharing — canonical https:// URLs (sitemap and canonicals today point at the HTTP S3 endpoint)
    • Foundation for API hosting — same custom-domain + TLS pattern applies when the deal matcher is deployed

RECOMMENDED ORDER OF OPERATIONS

  1. ACM certificate in us-east-1 for borrower.lenni.io
  2. CloudFront distribution → S3 website origin → redirect HTTP to HTTPS
  3. Route 53 alias record → CloudFront
  4. Rebuild site with https:// canonicals and sitemap URLs
  5. Separately: deploy deal matcher API and set LENNI_API_BASE
  6. Optionally: GitHub Actions for automated s3 sync

QUICK GLOSSARY (INFRASTRUCTURE TERMS)

  S3 — File storage; hosts static HTML. Static website hosting serves index.html for web requests.
  HTTP — Unencrypted protocol. What S3 website endpoints use today.
  HTTPS — Encrypted protocol. Requires TLS certificate via ACM on CloudFront.
  CloudFront — AWS CDN. Cache + HTTPS in front of S3.
  ACM — AWS Certificate Manager. Free SSL certificates for CloudFront and load balancers.
  Route 53 — AWS DNS. Maps lenni.io hostnames to CloudFront and other resources.
  IAM / AWS CLI — Identity and command-line tool for manual s3 sync deploys.
  CI/CD — Automated build and deploy on git events (not set up yet).
"""))

    sections.append(("AWS S3 bucket — every setting chosen", """
BUCKET CREATION (one-time setup, June 2026)

Bucket name: lenni-borrower
  S3 bucket names are globally unique across all AWS accounts. "lenni-borrower" was available and descriptive.

AWS Region: us-east-2 (Ohio)
  Originally the setup guide suggested us-east-1 (N. Virginia), but this bucket was created in us-east-2. The website endpoint format reflects that:
  http://lenni-borrower.s3-website.us-east-2.amazonaws.com

  All deploy commands must include --region us-east-2.

Object Ownership: Bucket owner preferred (default)
  The account that owns the bucket controls object ACLs.

BLOCK PUBLIC ACCESS — all four settings DISABLED
  For a public website, objects must be readable by anyone on the internet. In the S3 console under Permissions → Block public access:
    ☐ Block all public access — UNCHECKED (all four sub-options unchecked)
  AWS shows a warning when you do this. That is expected for public static sites.

BUCKET POLICY — public read for website objects
  A bucket policy grants s3:GetObject to Principal "*" (everyone) for all objects:

  {
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::lenni-borrower/*"
    }]
  }

  This allows browsers to download HTML, CSS, JS, and JSON files. It does NOT grant write access. Only authenticated IAM users with PutObject permission can upload.

STATIC WEBSITE HOSTING — enabled
  In S3 console → bucket lenni-borrower → Properties → Static website hosting → Enable.

  Hosting type: Host a static website
  Index document: index.html
  Error document: (optional — can leave blank or set to index.html for SPA-style routing)

  After enabling, AWS assigns the website endpoint URL (different from the REST API endpoint). Always use the website endpoint for browsing, not s3://lenni-borrower/index.html directly.
"""))

    sections.append(("IAM access — who can deploy and how", """
Two IAM users are documented in project sessions:

CONSOLE LOGIN (human browsing AWS)
  Account ID: 629603795749
  IAM username: adityaalldunkin
  Sign-in URL: https://629603795749.signin.aws.amazon.com/console

CLI DEPLOY USER (programmatic sync)
  IAM username: aditya-cli
  Access key type: Programmatic access (Access Key ID + Secret Access Key)
  Configured via: aws configure

DEPLOY IAM POLICY (custom policy: LenniBorrowerS3Deploy)
  Scoped to the lenni-borrower bucket only — not full AWS admin.

  Permissions granted:
    s3:ListBucket on arn:aws:s3:::lenni-borrower
    s3:GetObject on arn:aws:s3:::lenni-borrower/*
    s3:PutObject on arn:aws:s3:::lenni-borrower/*
    s3:DeleteObject on arn:aws:s3:::lenni-borrower/*

  ListBucket is needed for aws s3 sync to compare local vs remote.
  DeleteObject is needed when using --delete flag to remove stale files.

  The deploy user does NOT have s3:GetBucketWebsite, CloudFront, or Route53 permissions — those were configured separately in the console during initial setup.

AWS CLI INSTALLATION
  AWS CLI v2 installed on macOS via the official .pkg installer (AWSCLIV2.pkg).
  Verify: aws --version → aws-cli/2.x.x

AWS CLI CONFIGURATION
  aws configure
    Default region name: us-east-2
    Default output format: json
    Access Key ID: (from IAM security credentials tab)
    Secret Access Key: (shown once at key creation — store securely)
"""))

    sections.append(("Deploy procedure — step by step", f"""
Every site update follows the same two-step process: build locally, sync to S3.

STEP 1 — BUILD THE SITE LOCALLY

  cd /Users/adityarajiv/Documents/ffiec-cdr
  source .venv/bin/activate
  python ONLY_TEXAS_SINCE_2025/build_borrower_site.py

  This regenerates the entire borrower_site/ folder:
    {p['n_urls']} HTML pages, sitemap.xml, robots.txt, llms.txt, JSON data files.
  Typical build time: 2–5 seconds.

  Optional before build:
    python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py   # refresh bank contact data
    python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py --summary  # refresh FFIEC data

STEP 2 — SYNC TO S3

  aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete

  What this command does:
    borrower_site/ — local source folder (note trailing slash)
    s3://lenni-borrower/ — destination bucket root (note trailing slash)
    --region us-east-2 — must match bucket region
    --delete — removes S3 objects that no longer exist locally (keeps bucket in sync)

  Typical sync time: 10–30 seconds for ~{p['n_objects']} objects (~7 MB total).

STEP 3 — VERIFY

  Open {L} in a browser.
  Or: aws s3 ls s3://lenni-borrower/ --recursive --region us-east-2 | wc -l

DEPLOY HISTORY
  2026-06-10 — Initial single-file upload (2026-06-07-lenni-borrower-experience.html)
  2026-06-14 — Full multi-page site, 435 objects
  2026-06-18 — Bank enrichment redeploy
  2026-06-24 — Content expansion, 478 objects
"""))

    sections.append(("Common deployment problems we hit", """
404 NoSuchKey for index.html
  Cause: The borrower_site/ folder was uploaded as a subfolder inside the bucket, so S3 looked for lenni-borrower/index.html but the file was at lenni-borrower/borrower_site/index.html.
  Fix: Sync the contents of borrower_site/ to the bucket root, not the folder itself. The sync command above does this correctly because of the trailing slash on borrower_site/.

403 Forbidden
  Cause: Bucket policy missing, or Block Public Access still enabled, or index document not set in static website hosting.
  Fix: Verify all four Block Public Access checkboxes are off. Verify bucket policy grants s3:GetObject to "*". Verify static website hosting is enabled with index.html.

"Not secure" in Chrome
  Cause: S3 website endpoints serve HTTP only, not HTTPS. There is no TLS on the S3 website endpoint itself — browsers correctly label the connection as unencrypted.
  Context: Acceptable for this read-only demo (no login, no passwords, no payment forms). Visitors only download public HTML.
  Fix for production: Add CloudFront in front of S3, request an ACM certificate (us-east-1) for borrower.lenni.io, point Route 53 at CloudFront, and set viewer policy to redirect HTTP to HTTPS. See the detailed infrastructure sections earlier in this guide.

aws: command not found
  Cause: AWS CLI not installed or not on PATH.
  Fix: Install AWS CLI v2 via .pkg installer; restart terminal.

AccessDenied on sync
  Cause: IAM user lacks PutObject, DeleteObject, or ListBucket on the bucket.
  Fix: Attach LenniBorrowerS3Deploy policy (see previous section).

Sync interrupted / partial deploy
  Cause: Network interruption or approval timeout during long sync.
  Fix: Re-run the same sync command. aws s3 sync is idempotent — it resumes where it left off.
"""))

    sections.append(("Future hosting upgrades — action checklist", """
The current setup is intentionally minimal. The sections titled "HTTP, HTTPS, and the Not secure browser warning" through "Current architecture vs production target" explain each gap in plain English. This section is the condensed action checklist for when you are ready to build.

HTTPS VIA CLOUDFRONT
  1. Request ACM certificate in us-east-1 for borrower.lenni.io (DNS validation via Route 53)
  2. Create a CloudFront distribution
  3. Origin: lenni-borrower.s3-website.us-east-2.amazonaws.com (website endpoint, not REST endpoint)
  4. Viewer protocol policy: Redirect HTTP to HTTPS
  5. Attach the ACM certificate; add borrower.lenni.io as alternate domain name (CNAME)
  6. Create Route 53 A record (Alias) pointing borrower.lenni.io to the CloudFront distribution
  7. Rebuild the site and update sitemap and canonical URLs from http:// to https://

CUSTOM DOMAIN VIA ROUTE 53
  The lenni.io domain uses AWS Route 53 nameservers (confirmed in a separate session — not GoDaddy DNS for record edits).
  Subdomains discussed for Lenni products include borrower.lenni.io (this site) and convey.lenni.io (Convey app). Neither is wired to the lenni-borrower S3 bucket yet.

DEAL MATCHER API IN PRODUCTION
  Options documented: AWS Lambda + API Gateway, or a small EC2/ECS service.
  Frontend change: set window.LENNI_API_BASE in index.html to the production API URL.
  CORS origins already include the S3 website URL in api/main.py.
  Until deployed, "Match my deal" on the live site uses browser keyword fallback only.

CI/CD PIPELINE
  Proposed: GitHub Action on push to main → build_borrower_site.py → aws s3 sync.
  Requires: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in GitHub secrets.
  Not implemented as of June 2026 — all deploys remain manual via AWS CLI.
"""))

    sections.append(("What the site does not do — honest limitations", """
We would rather be clear about gaps than pretend the site is something it is not.

NO INTEREST RATES. Call Reports do not include pricing. Every rate is negotiated.

NO APPROVAL ODDS. Portfolio percentage is a fit signal, not a credit decision.

NO ONLINE APPLICATIONS. You contact the bank through their website or phone.

NO LOAN OFFICER DIRECTORY. We have phones for 208 banks from website scraping, but not named lenders.

QUARTERLY DATA LAG. The latest filing period is shown on every page. Banks can change strategy between quarters.

UNCLASSIFIED BALANCES. Some Call Report lines do not map cleanly to our eleven categories. They appear as "Unclassified" — not agriculture, not a separate product.

SCENARIO STORIES ARE EDUCATIONAL. They illustrate how to use the data. They are not financial advice.

HTTP ONLY. The live URL is not encrypted. Browsers show "Not secure" — expected for S3 website hosting without CloudFront. Do not enter passwords or sensitive personal data on the site — there is nowhere to enter them anyway. See the infrastructure sections in this guide for the CloudFront + HTTPS upgrade path.
"""))

    sections.append(("Step-by-step: your first hour on the site", f"""
SCENARIO A — You know you need a multifamily bridge loan in Dallas.

  1. Go to {L}
  2. Click Loan Types → Multifamily → Bridge guide
  3. Read "What to prepare" — gather rent roll, renovation budget, purchase contract
  4. Scroll to the bank table — note the top 5 banks by multifamily %
  5. Read Insight I-04 (specialist targeting) and I-12 (outreach planning)
  6. Open 3 bank profiles — check mix bars and Dallas branches
  7. Use the opening script from the bridge guide on your first call

SCENARIO B — You have a LoopNet listing but are not sure of the loan type.

  1. Copy the listing description (price, city, property type, size) from LoopNet — paste into "Match my deal" (a URL alone is not enough yet; see Match my deal sections)
  2. Review matched loan products in the workspace
  3. Click the top match to open the sub-type guide
  4. Follow the four-step preparation roadmap
  5. Call the top 3 recommended banks using the opening script from the guide

SCENARIO C — You want to understand the Texas market before calling anyone.

  1. Read Texas Market Overview
  2. Check Product Availability for your category
  3. Browse the ICP Bank Directory
  4. Read the Borrower Playbook cover to cover (~15 minutes)
  5. Pick the scenario story closest to your deal

SCENARIO D — Someone sent you a bank name and you want to vet them.

  1. Search the bank on Find Banks or go to /banks/{{id}}-{{name}}.html
  2. Study the portfolio mix — is your product a major line?
  3. Check branches in your market
  4. Compare to 2 competitors from the same loan type ranking table
"""))

    sections.append(("For developers — rebuilding and extending the site", """
SOURCE CODE LOCATION
  /Users/adityarajiv/Documents/ffiec-cdr/ONLY_TEXAS_SINCE_2025/

KEY FILES TO EDIT
  content/loan_products.yaml — all loan guide copy (7 parents, 27 sub-types)
  content/borrower_scenarios.yaml — 12 scenario stories
  borrower_content_engine.py — market pages, insights, scenarios, playbook
  build_borrower_site.py — main orchestrator (banks, cities, sitemap, deploy)
  build_borrower_website.py — interactive index.html template
  loan_mix.py — FFIEC line item → display category mapping
  bank_enrichment.py — website scrape merge logic

ARCHITECTURE
  No template engine (Jinja, etc.). All HTML is Python f-strings.
  SPA (index.html) embeds all bank data in a JavaScript DATA array (~1 MB).
  Static SEO pages are separate HTML files per bank, city, guide.
  patch_index_with_data() links SPA bank views to static profile pages.

ADD A NEW LOAN SUB-TYPE
  1. Add entry under the appropriate parent in loan_products.yaml
  2. Run build_borrower_site.py
  3. aws s3 sync ...

ADD A NEW SCENARIO STORY
  1. Add entry to content/borrower_scenarios.yaml
  2. Rebuild and deploy

REGENERATE THIS PDF
  python ONLY_TEXAS_SINCE_2025/build_borrower_website_guide.py

MASTER SESSION LOG
  session.md at repo root — full project history June 7–24, 2026
"""))

    sections.append(("S3 bucket folder structure (what lives where)", f"""
After a successful deploy, the lenni-borrower bucket contains {p['n_objects']} objects organized like this:

lenni-borrower/  (bucket root — NOT a borrower_site/ subfolder)
├── index.html              Main interactive app (~1.1 MB)
├── styles.css              Shared CSS for static pages
├── robots.txt              Search engine directives
├── sitemap.xml             {p['n_urls']} URLs
├── llms.txt                AI crawler index (summary)
├── llms-full.txt           AI crawler index (all bank URLs)
├── banks/                  {p['n_banks']} bank profile HTML files
├── cities/                 40 city landing pages
├── market/                 Texas overview, availability, asset bands, ICP directory
│   └── icp-banks/          Paginated ICP lists (page-2.html, page-3.html, …)
├── insights/               12 insight pages + index
├── scenarios/              12 scenario stories + index
├── guides/                 playbook, checklist, glossary, FAQ, methodology
├── loan-types/             7 parent hubs + 27 sub-type guides in subfolders
├── data/                   banks.json, loan_products.json, glossary.json, market_insights.json
└── js/                     match-client.js, workspace.js

CRITICAL: index.html must sit at the bucket root. The sync command uses a trailing slash on borrower_site/ so contents land at root, not inside a nested folder. This was the root cause of an early 404 error during initial setup.
"""))

    sections.append(("Bank website enrichment — the human layer on top of data", """
Starting June 18, 2026, bank profile pages include information scraped from each bank's public website. This sits on top of FFIEC/FDIC data — it does not replace it.

WHAT WAS SCRAPED
  344 Texas banks had a website URL in FDIC records.
  257 returned usable content after automated fetching.
  255 were matched to bank profiles and published.

WHAT YOU GET ON ENRICHED PROFILES
  About this bank — a short excerpt from the bank's meta description, with source URL and capture date.
  Contact and hours — phone numbers (208 banks), email addresses (44 banks), hours text when found.
  On the bank's website — deep links to commercial banking, contact, FAQ, and apply pages when discoverable.
  FAQ excerpts — only when the bank's site uses schema.org FAQPage JSON-LD (rare — just 2 banks).

HOW SCRAPING WORKS
  Script: scrape_bank_websites.py
  Fetches homepage plus one subpage (FAQ, commercial, or contact link if found).
  8 concurrent workers; full run takes about 54 seconds.
  User-Agent identifies the request as Lenni borrower research.
  Output: enrichment/bank_website_enrichment.json keyed by Federal Reserve RSSD ID.

LEGAL APPROACH
  Short excerpts only. Full answers link to the bank's site. Capture date shown for freshness. review_status: auto on all records — human QA recommended for ICP banks before sales use.

TO REFRESH
  python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py
  python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
  aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
"""))

    sections.append(("Interactive features on the home page", """
Beyond "Match my deal," the home page includes several tools worth knowing about.

FIND BANKS VIEW
  Filter {n_banks} banks by metro area, asset size, and loan specialty. Sort by assets or portfolio concentration. Click any bank to open its full profile page.

LOAN TYPES VIEW
  Seven category cards with sub-type counts. Drill into a category to see sub-type chips, a plain-English explanation, and a live ranking of specialist banks. Links to full static guide pages for SEO.

AI TERMINAL
  A chat-style interface where you type questions in plain English. Today it uses keyword routing — if you mention "apartment" and "bridge," it routes toward multifamily content. It is a stub for a fuller roadmap/chat experience planned with Monday.com data and call recording insights. Not a replacement for professional advice.

PORTFOLIO CALCULATOR (on loan product views)
  Enter a loan amount and see how it compares to typical bank exposure in that category. Helps answer "is my deal big enough to matter to this bank?"

STATIC VS INTERACTIVE
  The interactive app is convenient for exploration. Static HTML pages (banks/, loan-types/, insights/) are better for Google indexing, sharing direct links, and printing. The build script links them together — clicking a bank in the app opens its static profile.
""".replace("{n_banks}", str(p['n_banks']))))

    sections.append(("Post-deploy verification checklist", f"""
Run through this list after every aws s3 sync to confirm the deploy worked.

BROWSER CHECKS
  ☐ {L} loads the home page (not 403 or 404)
  ☐ Click Texas Market → overview page loads
  ☐ Click Insights → 12 cards visible
  ☐ Click a bank profile → portfolio mix chart renders
  ☐ Click a loan sub-type guide (e.g. multifamily/bridge) → bank table present

CLI CHECKS
  ☐ aws s3 ls s3://lenni-borrower/ --region us-east-2  → shows index.html at root
  ☐ aws s3 ls s3://lenni-borrower/insights/ --region us-east-2  → 13 files
  ☐ aws s3 ls s3://lenni-borrower/market/ --region us-east-2  → overview + ICP pages
  ☐ aws s3 ls s3://lenni-borrower/ --recursive --region us-east-2 | wc -l  → ~{p['n_objects']} objects

DATA FRESHNESS
  ☐ Home page banner shows period ending {p['period']}
  ☐ sitemap.xml dated today (check Last modified in S3 console)
  ☐ data/banks.json file size reasonable (~few MB)

COMMON FAILURES
  404 on home → index.html not at bucket root (see deployment troubleshooting section)
  403 on pages → bucket policy or public access block misconfigured
  Old content showing → hard-refresh browser (Cmd+Shift+R) or check sync actually ran
"""))

    sections.append(("Glossary and FAQ pages — when to use them", f"""
GLOSSARY ({L}/guides/glossary.html)

If you are reading a bank profile and see "RCON1460" or "C&I" or "RCON2122" and are not sure what it means, open the glossary. It translates Federal Reserve regulatory codes into plain English.

Examples:
  RCON2122 — Total loans and leases (the denominator for all portfolio percentages)
  RCON1460 — Multifamily real estate (5+ unit apartments)
  RCONF161 — Investor income property (non-owner-occupied CRE)
  RCONF160 — Owner-occupied commercial real estate
  RCON1766 — Commercial and industrial (business) loans

The glossary is built from texas_loan_products_mdrm_catalog.csv — 24,000+ MDRM code definitions filtered to terms that appear in Texas Call Report data.

FAQ ({L}/guides/faq.html)

Eight questions covering the basics: what the site is, where data comes from, whether you can apply for a loan here, what a community bank is, and the difference between HQ city and branch footprint. Send this link to anyone who asks "what is Lenni Borrower?"
"""))

    return sections
