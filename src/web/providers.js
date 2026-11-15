"use strict";

// Operator credentials live only in this page's memory; never localStorage/cookies/URLs.
let operatorToken = "";
let experimentalResult = null;
let researchGeneration = 0;
const settingsDialog = document.querySelector("#settings-dialog");
const providerNames = {context: "Context.dev", cala: "Cala.ai", featherless: "Featherless", verda: "Verda (NVIDIA only)"};
const providerNotes = {
  context: "Optional publisher news search. Up to 10 articles per request; existing daily credit limits apply.",
  cala: "Experimental ownership research: one focused question about the named entity. Reference IDs may not link to original sources. Treat answers as unverified leads. Application cap: 90 calls per rolling 30 days.",
  featherless: "Experimental evidence review. Enter an exact model ID available on your plan. Test access checks your account and model catalog without generating text.",
  verda: "NVIDIA-authored models only. Use the exact NVIDIA model ID and the endpoint supplied by Verda (containers.verda.com or containers.datacrunch.io). The GPU scales to zero when idle; starting it can take several minutes. No GPU deployment is created by saving these settings."
};

function secureSettingsPage() {
  return location.protocol === "https:" || ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
}

async function operatorApi(path, options = {}) {
  if (!secureSettingsPage()) throw new Error("Use HTTPS or an SSH tunnel before sending credentials.");
  if (!operatorToken) throw new Error("Open Settings and unlock with the operator token first.");
  return api(path, {...options, cache: "no-store", headers: {"Content-Type": "application/json", "X-Noise-Operator": operatorToken, ...(options.headers || {})}});
}

function field(container, title, type, value = "") {
  const label = element("label", "field-label block mt-3", title);
  const input = document.createElement("input");
  input.type = type;
  input.className = "field-control mt-1";
  input.value = value;
  if (type === "password") input.autocomplete = "new-password";
  label.append(input);
  container.append(label);
  return input;
}

function showProviders(providers) {
  const container = $("#provider-settings");
  container.replaceChildren();
  for (const provider of providers) {
    const form = element("form", "rounded-xl bg-surface-container-lowest p-4");
    form.dataset.provider = provider.id;
    form.append(element("h3", "font-semibold", providerNames[provider.id]));
    form.append(element("p", "mt-1 text-body-sm text-outline", providerNotes[provider.id]));
    const status = element("p", "mt-2 text-body-sm text-primary", provider.key_configured ? "API key saved" : "No API key configured");
    status.dataset.keyStatus = "";
    form.append(status);
    const key = field(form, "API key (leave blank to keep)", "password");
    key.maxLength = 512;
    const enableLabel = element("label", "mt-3 flex items-center gap-2");
    const enabled = document.createElement("input"); enabled.type = "checkbox"; enabled.checked = provider.enabled;
    enableLabel.append(enabled, document.createTextNode(provider.id === "context" ? "Enable Context.dev news search" : "Enable experimental provider"));
    form.append(enableLabel);
    const removeLabel = element("label", "mt-2 flex items-center gap-2 text-body-sm");
    const remove = document.createElement("input"); remove.type = "checkbox";
    removeLabel.append(remove, document.createTextNode("Remove saved key")); form.append(removeLabel);
    const model = ["verda", "featherless"].includes(provider.id) ? field(form, "Exact model ID", "text", provider.model) : null;
    const base = provider.id === "verda" ? field(form, "Verda API base URL (including /v1)", "url", provider.base_url) : null;
    const buttons = element("div", "mt-3 flex gap-2");
    const save = element("button", "rounded-lg bg-primary-container px-3 py-2 text-on-primary", "Save settings"); save.type = "submit";
    buttons.append(save);
    const feedback = element("p", "mt-2 whitespace-pre-wrap break-words text-body-sm text-tertiary"); feedback.setAttribute("role", "status");
    if (["featherless", "verda"].includes(provider.id)) {
      const test = element("button", "rounded-lg bg-surface-container-high px-3 py-2", "Test saved access"); test.type = "button";
      test.onclick = async () => {
        test.disabled = true; feedback.textContent = "Checking saved credentials and available models… Verda may need several minutes to start.";
        try {
          const result = await operatorApi(`/api/settings/${provider.id}/test`, {method: "POST"});
          feedback.textContent = result.message + (result.models?.length ? `\nAvailable model IDs: ${result.models.join(", ")}` : "");
        } catch (error) { feedback.textContent = error.message; }
        finally { test.disabled = false; }
      };
      buttons.append(test);
    }
    form.append(buttons, feedback);
    form.onsubmit = async (event) => {
      event.preventDefault(); save.disabled = true;
      const patch = {api_key: key.value, remove_key: remove.checked, enabled: enabled.checked};
      if (model) patch.model = model.value.trim();
      if (base) patch.base_url = base.value.trim();
      try {
        const saved = await operatorApi(`/api/settings/${provider.id}`, {method: "PATCH", body: JSON.stringify(patch)});
        key.value = ""; remove.checked = false;
        status.textContent = saved.key_configured ? "API key saved" : "No API key configured";
        feedback.textContent = "Saved. Credentials have not been validated unless you test access or run a request.";
        checkSources();
      } catch (error) { feedback.textContent = error.message; }
      finally { save.disabled = false; }
    };
    container.append(form);
  }
}

$("#settings-button").onclick = () => { settingsDialog.showModal(); $("#operator-token").focus(); };
$("#settings-close").onclick = () => { settingsDialog.close(); document.querySelectorAll('#settings-dialog input[type="password"]').forEach(input => { input.value = ""; }); };
settingsDialog.addEventListener("cancel", () => document.querySelectorAll('#settings-dialog input[type="password"]').forEach(input => { input.value = ""; }));
$("#settings-unlock").onsubmit = async (event) => {
  event.preventDefault();
  operatorToken = $("#operator-token").value; $("#operator-token").value = "";
  try {
    const result = await operatorApi("/api/settings");
    showProviders(result.providers);
    $("#settings-unlock").classList.add("hidden"); $("#settings-lock").classList.remove("hidden");
    $("#settings-status").textContent = "Unlocked. Experimental calls are limited to 4 operations/minute and 20/day per provider, including failed calls and access tests.";
  } catch (error) { operatorToken = ""; $("#settings-status").textContent = error.message; }
};
$("#settings-lock").onclick = () => {
  operatorToken = ""; $("#provider-settings").replaceChildren();
  $("#settings-unlock").classList.remove("hidden"); $("#settings-lock").classList.add("hidden");
  $("#settings-status").textContent = "Locked.";
};

function renderExperimental(result) {
  const container = $("#review-result"); container.replaceChildren();
  container.append(element("h3", "font-semibold", `${providerNames[result.provider]} · ${result.entity}${result.model ? ` · ${result.model}` : ""}`));
  container.append(element("p", "text-body-sm text-tertiary", result.notice));
  if (result.synthetic) container.append(element("p", "text-primary", "Synthetic input: these are fictional demonstration records."));
  if (result.kind === "research") {
    if (result.query) container.append(element("p", "text-body-sm text-outline", `Question sent to Cala: ${result.query}`));
    container.append(element("p", "whitespace-pre-wrap break-words", result.content));
    container.append(element("p", "text-body-sm text-tertiary", result.reference_notice));
    for (const ref of result.references || []) container.append(element("p", "whitespace-pre-wrap break-words text-body-sm text-outline", `Cala reference ${ref.id}: ${ref.content}`));
  } else {
    container.append(element("p", "text-body-sm", `Entity match suggested by model: ${result.relevance}. Records reviewed: ${result.records_reviewed}.`));
    if (!result.findings.length) container.append(element("p", "text-body-sm", "No findings with valid evidence quotes were returned. This does not establish that connections are absent."));
    for (const finding of result.findings) {
      const card = element("article", "rounded-xl bg-surface-container-lowest p-3");
      card.append(element("p", "text-outline text-body-sm", `AI hypothesis · ${finding.category.replaceAll("_", " ")}`));
      card.append(element("p", "mt-1", finding.claim));
      for (const citation of finding.evidence) {
        card.append(element("blockquote", "mt-2 border-l-2 border-primary pl-3 text-body-sm", citation.quote));
        if (citation.source_url) {
          const link = element("a", "text-primary text-body-sm", `Open record ${citation.id}`);
          link.href = citation.source_url; link.target = "_blank"; link.rel = "noopener noreferrer"; card.append(link);
        } else card.append(element("p", "text-body-sm text-outline", `Record ${citation.id} · original URL unavailable`));
      }
      container.append(card);
    }
    if (result.discarded_findings) container.append(element("p", "text-body-sm text-outline", `${result.discarded_findings} claims omitted because their evidence references or quotes were invalid.`));
    container.append(element("p", "text-body-sm text-outline", "Quotes are checked against supplied records. Their truth and whether they support the model’s claim still require human review."));
  }
}

$("#review-form").onsubmit = async (event) => {
  event.preventDefault();
  const button = $("#review-button"); button.disabled = true;
  experimentalResult = null; $("#review-export").disabled = true; $("#review-result").replaceChildren();
  $("#review-status").textContent = "Requesting an experimental review…";
  const provider = $("#review-provider").value;
  if (provider === "verda") $("#review-status").textContent = "Requesting the NVIDIA review… Verda may take several minutes to start after being idle. Keep this page open; the request is submitted once.";
  if (provider === "cala") $("#review-status").textContent = "Researching with Cala… This may take a minute or two. Keep this page open; the request is submitted once.";
  const generation = researchGeneration;
  const events = provider === "cala" ? [] : latestEvents.slice(0, 20).map(item => ({id: String(item.id).slice(0,500), text: String(item.text).slice(0,12000), source_url: item.source_url || null, timestamp: item.timestamp || "", publisher: item.publisher || null}));
  try {
    const result = await operatorApi("/api/experimental/review", {method: "POST", body: JSON.stringify({provider, entity: $("#review-entity").value.trim(), events, synthetic: provider !== "cala" && !!latestReport?.synthetic})});
    if (generation !== researchGeneration) return;
    experimentalResult = result; renderExperimental(result); $("#review-export").disabled = false;
    $("#review-status").textContent = `Completed at ${new Date(result.created_at).toLocaleString()}. ${provider === "cala" ? "Cala ownership research" : "Only the submitted records were reviewed; no external web search was performed"}.`;
  } catch (error) { if (generation === researchGeneration) $("#review-status").textContent = error.message; }
  finally { button.disabled = false; }
};
document.addEventListener("noise:report", () => {
  researchGeneration += 1;
  experimentalResult = null;
  $("#review-export").disabled = true;
  $("#review-result").replaceChildren();
  $("#review-status").textContent = "New investigation loaded. Run a review for these records.";
});
$("#review-export").onclick = () => {
  if (!experimentalResult) return;
  const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([JSON.stringify(experimentalResult, null, 2)], {type: "application/json"}));
  link.download = "experimental-company-research.json"; link.click(); URL.revokeObjectURL(link.href);
};
