// Accordion logic
document.querySelectorAll('.f1-accordion-header').forEach((btn, idx) => {
  btn.addEventListener('click', function() {
    if (btn.disabled) return;
    document.querySelectorAll('.f1-accordion-section').forEach((sec, sidx) => {
      sec.setAttribute('aria-expanded', sidx === idx ? 'true' : 'false');
    });
    document.querySelectorAll('.f1-step').forEach((step, sidx) => {
      step.classList.toggle('active', sidx === idx);
    });
  });
});

// Stepper click (optional, for navigation)
document.querySelectorAll('.f1-step').forEach((step, idx) => {
  step.addEventListener('click', () => {
    const sec = document.getElementById('step'+idx);
    if (sec && !sec.querySelector('.f1-accordion-header').disabled)
      sec.querySelector('.f1-accordion-header').click();
  });
});

// Step logic
const yearSel = document.getElementById('year');
const raceSel = document.getElementById('race');
const driver1Sel = document.getElementById('driver1');
const driver2Sel = document.getElementById('driver2');
const summary = document.getElementById('summary');
const submitBtn = document.getElementById('submitBtn');
const resetBtn = document.getElementById('resetBtn');
const driverLoadingSpinner = document.getElementById('driver-loading-spinner');

yearSel.addEventListener('change', function() {
  // Reset following steps
  raceSel.innerHTML = '<option value="">Select Grand Prix...</option>';
  driver1Sel.innerHTML = '<option value="">Select first driver...</option>';
  driver2Sel.innerHTML = '<option value="">Select second driver...</option>';
  [raceSel, driver1Sel, driver2Sel].forEach(sel => sel.disabled = true);
  document.getElementById('step1').querySelector('.f1-accordion-header').disabled = true;
  document.getElementById('step2').querySelector('.f1-accordion-header').disabled = true;
  submitBtn.disabled = true;
  summary.style.display = 'none';

  if (!this.value) return;

  // Accordion animation: collapse step0, expand step1, update stepper
  document.getElementById('step0').setAttribute('aria-expanded', 'false');
  document.getElementById('step1').setAttribute('aria-expanded', 'true');
  document.querySelectorAll('.f1-step').forEach((step, idx) => {
    step.classList.toggle('active', idx === 1);
  });

  // Load races for the selected year
  fetch('/get_races', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: `year=${this.value}`
  })
  .then(r => r.json())
  .then(data => {
    if (data.races && data.races.length) {
      data.races.forEach(race => {
        const opt = document.createElement('option');
        opt.value = race.event_name;
        opt.textContent = `${race.country} (${race.event_name})`;
        raceSel.appendChild(opt);
      });
      raceSel.disabled = false;
      document.getElementById('step1').querySelector('.f1-accordion-header').disabled = false;
    }
  });
});

raceSel.addEventListener('change', function() {
  // Reset drivers
  driver1Sel.innerHTML = '<option value="">Select first driver...</option>';
  driver2Sel.innerHTML = '<option value="">Select second driver...</option>';
  [driver1Sel, driver2Sel].forEach(sel => sel.disabled = true);
  document.getElementById('step2').querySelector('.f1-accordion-header').disabled = true;
  submitBtn.disabled = true;
  summary.style.display = 'none';

  if (!this.value || !yearSel.value) return;

  // Accordion animation: collapse step1, expand step2, update stepper (IMMEDIATELY)
  document.getElementById('step1').setAttribute('aria-expanded', 'false');
  document.getElementById('step2').setAttribute('aria-expanded', 'true');
  document.querySelectorAll('.f1-step').forEach((step, idx) => {
    step.classList.toggle('active', idx === 2);
  });

  // Show spinner
  driverLoadingSpinner.style.display = '';
  // Load drivers for the selected race (always "Race" session for simplicity)
  fetch('/get_drivers', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: `year=${yearSel.value}&race=${encodeURIComponent(this.value)}&session=Race`
  })
  .then(r => r.json())
  .then(data => {
    driverLoadingSpinner.style.display = 'none';
    if (data.drivers && data.drivers.length) {
      data.drivers.forEach(driver => {
        const opt1 = document.createElement('option');
        opt1.value = driver.abbreviation;
        opt1.textContent = driver.broadcast_name;
        driver1Sel.appendChild(opt1);
        const opt2 = document.createElement('option');
        opt2.value = driver.abbreviation;
        opt2.textContent = driver.broadcast_name;
        driver2Sel.appendChild(opt2);
      });
      driver1Sel.disabled = false;
      driver2Sel.disabled = false;
      document.getElementById('step2').querySelector('.f1-accordion-header').disabled = false;
    }
  })
  .catch(() => {
    driverLoadingSpinner.style.display = 'none';
  });
});

function updateSummary() {
  if (
    yearSel.value &&
    raceSel.value &&
    driver1Sel.value &&
    driver2Sel.value &&
    driver1Sel.value !== driver2Sel.value
  ) {
    summary.innerHTML = `
      <div>
        <strong>Year:</strong> ${yearSel.value}<br>
        <strong>Grand Prix:</strong> ${raceSel.options[raceSel.selectedIndex].text}<br>
        <strong>Driver 1:</strong> ${driver1Sel.options[driver1Sel.selectedIndex].text}<br>
        <strong>Driver 2:</strong> ${driver2Sel.options[driver2Sel.selectedIndex].text}
      </div>
    `;
    summary.style.display = '';
    submitBtn.disabled = false;
  } else {
    summary.style.display = 'none';
    submitBtn.disabled = true;
  }
}
[driver1Sel, driver2Sel].forEach(sel => sel.addEventListener('change', updateSummary));

// Prevent same driver selection
[driver1Sel, driver2Sel].forEach(sel => sel.addEventListener('change', function() {
  if (driver1Sel.value && driver2Sel.value && driver1Sel.value === driver2Sel.value) {
    submitBtn.disabled = true;
    summary.style.display = 'none';
  }
}));

// Reset
resetBtn.addEventListener('click', function() {
  f1Form.reset();
  [raceSel, driver1Sel, driver2Sel].forEach(sel => {
    sel.innerHTML = sel.options[0].outerHTML;
    sel.disabled = true;
  });
  document.querySelectorAll('.f1-accordion-section').forEach((sec, idx) => {
    sec.setAttribute('aria-expanded', idx === 0 ? 'true' : 'false');
    sec.querySelector('.f1-accordion-header').disabled = idx > 0;
  });
  document.querySelectorAll('.f1-step').forEach((step, idx) => step.classList.toggle('active', idx === 0));
  summary.style.display = 'none';
  submitBtn.disabled = true;
});

// On submit, accordion closes and button disables
document.getElementById('f1Form').addEventListener('submit', function() {
  submitBtn.disabled = true;
});
