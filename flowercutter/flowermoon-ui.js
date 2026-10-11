/* Accessibility for the presentation layer; no nesting data or calculations. */
(() => {
  const names = {trimToggle:'Trim edges', lsShowLabels:'Show labels', lsColour:'Colour highlighting'};
  Object.entries(names).forEach(([id, name]) => {
    const toggle = document.getElementById(id);
    if (!toggle) return;
    toggle.tabIndex = 0;
    toggle.setAttribute('role', 'switch');
    toggle.setAttribute('aria-label', name);
    const sync = () => toggle.setAttribute('aria-checked', String(toggle.classList.contains('on')));
    sync();
    new MutationObserver(sync).observe(toggle, {attributes:true, attributeFilter:['class']});
    toggle.addEventListener('keydown', event => {
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault();
        toggle.click();
      }
    });
  });
  const labelInputs = root => {
    root.querySelectorAll('input[placeholder]').forEach(input => {
      input.setAttribute('aria-label', input.placeholder);
    });
    root.querySelectorAll('button.btn-del, #stockSheetList button').forEach(button => {
      const label = button.closest('.piece-row')?.querySelector('input')?.value;
      button.setAttribute('aria-label', button.classList.contains('btn-del') ? `Remove part${label ? ' ' + label : ''}` : 'Remove stock size');
    });
  };
  labelInputs(document);
  ['piecesList','stockSheetList'].forEach(id => {
    const root = document.getElementById(id);
    if (root) new MutationObserver(() => labelInputs(document)).observe(root, {childList:true,subtree:true});
  });
  document.querySelectorAll('.field').forEach(field => {
    const label = field.querySelector('label');
    const control = field.querySelector('input,select');
    if (label && control && control.id) label.htmlFor = control.id;
  });
  const settings = document.getElementById('btnLayoutSettings');
  settings?.setAttribute('aria-controls', 'layoutSettingsBar');
  const syncSettings = () => settings?.setAttribute('aria-expanded', String(document.getElementById('layoutSettingsBar')?.classList.contains('open')));
  syncSettings();
  settings?.addEventListener('click', syncSettings);
})();
