// EN / 繁中 language toggle (added by build_glp1_site.py)
(function () {
  function setLang(l) {
    document.body.classList.remove('lang-en', 'lang-zh');
    document.body.classList.add('lang-' + l);
    document.querySelectorAll('.lang-btn').forEach(function (b) {
      var on = b.getAttribute('data-lang') === l;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    document.documentElement.lang = (l === 'zh') ? 'zh-Hant-TW' : 'en';
    try { localStorage.setItem('glp1-lang', l); } catch (e) {}
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.lang-btn');
    if (b) setLang(b.getAttribute('data-lang'));
  });
  var saved = 'zh';
  try { saved = localStorage.getItem('glp1-lang') || 'zh'; } catch (e) {}
  setLang(saved);
})();
