/* apps/web/app.js — fetch verified clinics from the Core API and render them as cards.
   Read-only by design: no login, no write calls — this is a credibility page for investors/partners. */
(function () {
  "use strict";

  var API_BASE = (window.VETLINK_API_BASE || "").replace(/\/$/, "");
  var API_URL = API_BASE + "/api/v1/clinics/";

  var statusEl = document.getElementById("status");
  var gridEl = document.getElementById("grid");

  function setStatus(message, isError) {
    statusEl.textContent = message;
    statusEl.classList.toggle("error", Boolean(isError));
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function card(clinic) {
    var services = Array.isArray(clinic.services) ? clinic.services : [];
    var servicesHtml =
      services.length > 0
        ? "<ul class='services'>" +
          services
            .map(function (s) {
              return "<li>" + escapeHtml(s) + "</li>";
            })
            .join("") +
          "</ul>"
        : "<p class='meta'>No listed services</p>";

    return (
      "<article class='card'>" +
      "<h2>" +
      escapeHtml(clinic.name) +
      "</h2>" +
      "<p class='meta'>" +
      escapeHtml(clinic.county || "County not listed") +
      (clinic.sub_county ? " · " + escapeHtml(clinic.sub_county) : "") +
      "</p>" +
      (clinic.unique_code ? "<span class='code'>" + escapeHtml(clinic.unique_code) + "</span><br/>" : "") +
      servicesHtml +
      "</article>"
    );
  }

  fetch(API_URL)
    .then(function (resp) {
      if (!resp.ok) {
        throw new Error("API returned HTTP " + resp.status);
      }
      return resp.json();
    })
    .then(function (clinics) {
      var verified = (clinics || []).filter(function (c) {
        return c.verification_status === "verified";
      });
      if (verified.length === 0) {
        setStatus("");
        gridEl.innerHTML =
          "<div class='empty'>No verified clinics listed yet. Check back soon.</div>";
        return;
      }
      setStatus(verified.length + " verified clinic" + (verified.length === 1 ? "" : "s") + " shown.");
      gridEl.innerHTML = verified.map(card).join("");
    })
    .catch(function (err) {
      setStatus("Could not load clinics: " + err.message, true);
    });
})();