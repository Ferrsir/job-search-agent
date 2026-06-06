(() => {
  const compact = (value) => (value || "").replace(/\s+/g, " ").trim();

  const textFrom = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const text = compact(node?.innerText || node?.textContent || node?.getAttribute?.("content"));
      if (text) return text;
    }
    return "";
  };

  const meta = (names) => {
    for (const name of names) {
      const node = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
      const value = compact(node?.getAttribute("content"));
      if (value) return value;
    }
    return "";
  };

  const splitTitle = (pageTitle) => {
    const cleaned = compact(pageTitle)
      .replace(/\s+\|\s+LinkedIn.*$/i, "")
      .replace(/\s+-\s+LinkedIn.*$/i, "")
      .replace(/\s+\|\s+Handshake.*$/i, "")
      .replace(/\s+-\s+Handshake.*$/i, "");
    const separators = [" at ", " @ ", " - ", " | "];
    for (const separator of separators) {
      const pieces = cleaned.split(separator).map(compact).filter(Boolean);
      if (pieces.length >= 2) {
        return { title: pieces[0], company: pieces[1] };
      }
    }
    return { title: cleaned, company: "" };
  };

  const visibleBodyText = () => compact(document.body?.innerText || "").slice(0, 7000);

  const inferCompany = () => {
    const explicit = textFrom([
      "[data-test-job-company-name]",
      "[data-testid='company-name']",
      ".jobs-unified-top-card__company-name",
      ".topcard__org-name-link",
      ".job-details-jobs-unified-top-card__company-name",
      ".company-name",
      ".posting-company",
      ".department",
      "[class*='company'] a",
      "[class*='Company'] a"
    ]);
    if (explicit) return explicit;

    const ogSite = meta(["og:site_name", "twitter:site"]);
    if (ogSite && !/linkedin|handshake|greenhouse|lever|ashby|workday|smartrecruiters/i.test(ogSite)) {
      return ogSite.replace(/^@/, "");
    }

    const host = location.hostname.replace(/^www\./, "");
    if (/jobs\.lever\.co/i.test(host)) {
      const [, company] = location.pathname.split("/");
      return compact(company || "");
    }
    if (/boards\.greenhouse\.io/i.test(host)) {
      const [, company] = location.pathname.split("/");
      return compact(company || "");
    }
    return "";
  };

  const inferLocation = () => textFrom([
    "[data-test-job-location]",
    "[data-testid='job-location']",
    ".jobs-unified-top-card__bullet",
    ".job-details-jobs-unified-top-card__primary-description-container",
    ".topcard__flavor--bullet",
    ".posting-categories",
    "[class*='location']",
    "[class*='Location']"
  ]);

  const inferTitle = () => {
    const explicit = textFrom([
      "h1",
      "[data-test-job-title]",
      "[data-testid='job-title']",
      ".jobs-unified-top-card__job-title",
      ".job-details-jobs-unified-top-card__job-title",
      ".topcard__title",
      ".posting-headline h2",
      ".job-title"
    ]);
    if (explicit) return explicit;
    return splitTitle(document.title).title;
  };

  const inferRequirements = (body) => {
    const lower = body.toLowerCase();
    const starts = [
      "basic qualifications",
      "minimum qualifications",
      "requirements",
      "what you'll bring",
      "what you’ll bring",
      "qualifications",
      "you have",
      "required skills"
    ];
    const start = starts.map((marker) => lower.indexOf(marker)).filter((index) => index >= 0).sort((a, b) => a - b)[0];
    if (start === undefined) return "";
    return compact(body.slice(start, start + 1200));
  };

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "extract-job") return false;

    const body = visibleBodyText();
    const fromTitle = splitTitle(document.title);
    const title = inferTitle() || fromTitle.title;
    const company = inferCompany() || fromTitle.company;
    const locationText = inferLocation();
    const description = meta(["og:description", "description", "twitter:description"]);

    sendResponse({
      title,
      company,
      location: locationText,
      url: location.href,
      source: location.hostname.includes("linkedin") ? "LinkedIn manual save"
        : location.hostname.includes("handshake") ? "Handshake manual save"
        : "Browser Extension",
      fitSummary: "Manually saved from browser extension; needs fit review.",
      requirements: inferRequirements(body) || description,
      pageTitle: document.title,
      selectedText: compact(window.getSelection?.().toString?.() || ""),
      rawText: body.slice(0, 2500)
    });
    return true;
  });
})();
