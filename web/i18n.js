/* Shared UI/API catalogue. Only application text is translated, never scene data. */
'use strict';
const I18n = (() => {
  const messages = window.DISPATCH_MESSAGES;
  const seen = new Map();
  const missing = new Set();
  let language = 'en';
  try {
    const saved = localStorage.getItem('dispatch.language');
    if (saved === 'en' || saved === 'zh-Hant') language = saved;
  } catch (_) { /* Private/restricted storage still uses English. */ }
  function has(key) { return Object.hasOwn(messages.en, key); }
  function t(key, params = {}) {
    if (!has(key)) { missing.add(key); return `[${key}]`; }
    const value = messages[language][key].replace(/\{(\w+)\}/g,
      (_, name) => params[name] === undefined ? `{${name}}` : String(params[name]));
    seen.set(value, {code:key, params:{...params}});
    return value;
  }
  function descriptor(value) {
    if (value && typeof value === 'object' && value.code) return value;
    return seen.get(value) || {text:String(value ?? '')};
  }
  function render(value) {
    const d = descriptor(value);
    return d.code ? t(d.code, d.params) : d.text;
  }
  function apply(root = document) {
    root.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.dataset.i18n);
    });
    for (const attr of ['title','aria-label','placeholder']) {
      root.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => {
        el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`)));
      });
    }
    document.documentElement.lang = language;
    document.title = language === 'en' ? 'Dispatch Lab · Route Editor' : 'Dispatch Lab · 路線編輯器';
  }
  function setLanguage(value) {
    if (!Object.hasOwn(messages, value)) return;
    language = value;
    try { localStorage.setItem('dispatch.language', value); } catch (_) { }
    apply();
    document.dispatchEvent(new CustomEvent('languagechange', {detail:{language}}));
  }
  return {t, has, descriptor, render, apply, setLanguage, missing,
          get language() { return language; }, messages};
})();
I18n.apply();
