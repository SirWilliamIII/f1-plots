document.addEventListener('DOMContentLoaded', function () {
  // ========== INDEX PAGE LOGIC ==========

  if (document.body.id === 'index-body') {
    // Accordion logic

    document.querySelectorAll('.f1-accordion-header').forEach((btn, idx) => {
      btn.addEventListener('click', function () {
        if (btn.disabled) return

        document

          .querySelectorAll('.f1-accordion-section')

          .forEach((sec, sidx) => {
            sec.setAttribute('aria-expanded', sidx === idx ? 'true' : 'false')
          })

        document.querySelectorAll('.f1-step').forEach((step, sidx) => {
          step.classList.toggle('active', sidx === idx)
        })
      })
    })

    // Stepper click (optional, for navigation)

    document.querySelectorAll('.f1-step').forEach((step, idx) => {
      step.addEventListener('click', () => {
        const sec = document.getElementById('step' + idx)

        if (sec && !sec.querySelector('.f1-accordion-header').disabled)
          sec.querySelector('.f1-accordion-header').click()
      })
    })

    // Step logic

    const yearSel = document.getElementById('year')

    const raceSel = document.getElementById('race')

    const driver1Sel = document.getElementById('driver1')

    const driver2Sel = document.getElementById('driver2')

    const summary = document.getElementById('summary')

    const submitBtn = document.getElementById('submitBtn')

    const resetBtn = document.getElementById('resetBtn')

    const driverLoadingSpinner = document.getElementById('driver-loading-spinner')

    yearSel.addEventListener('change', function () {
      // Reset following steps

      raceSel.innerHTML = '<option value="">Select Grand Prix...</option>'

      driver1Sel.innerHTML = '<option value="">Select first driver...</option>'

      driver2Sel.innerHTML = '<option value="">Select second driver...</option>'

      ;[raceSel, driver1Sel, driver2Sel].forEach((sel) => (sel.disabled = true))

      document

        .getElementById('step1')

        .querySelector('.f1-accordion-header').disabled = true

      document

        .getElementById('step2')

        .querySelector('.f1-accordion-header').disabled = true

      submitBtn.disabled = true

      summary.style.display = 'none'

      if (!this.value) return

      // Accordion animation: collapse step0, expand step1, update stepper

      document.getElementById('step0').setAttribute('aria-expanded', 'false')

      document.getElementById('step1').setAttribute('aria-expanded', 'true')

      document.querySelectorAll('.f1-step').forEach((step, idx) => {
        step.classList.toggle('active', idx === 1)
      })

      // Load races for the selected year

      fetch('/get_races', {
        method: 'POST',

        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },

        body: `year=${this.value}`
      })
        .then((r) => r.json())

        .then((data) => {
          if (data.races && data.races.length) {
            data.races.forEach((race) => {
              const opt = document.createElement('option')

              opt.value = race.event_name

              opt.textContent = `${race.country} (${race.event_name})`

              raceSel.appendChild(opt)
            })

            raceSel.disabled = false

            document

              .getElementById('step1')

              .querySelector('.f1-accordion-header').disabled = false
          }
        })
    })

    raceSel.addEventListener('change', function () {
      // Reset drivers

      driver1Sel.innerHTML = '<option value="">Select first driver...</option>'

      driver2Sel.innerHTML = '<option value="">Select second driver...</option>'

      ;[driver1Sel, driver2Sel].forEach((sel) => (sel.disabled = true))

      document

        .getElementById('step2')

        .querySelector('.f1-accordion-header').disabled = true

      submitBtn.disabled = true

      summary.style.display = 'none'

      if (!this.value || !yearSel.value) return

      // Accordion animation: collapse step1, expand step2, update stepper (IMMEDIATELY)

      document.getElementById('step1').setAttribute('aria-expanded', 'false')

      document.getElementById('step2').setAttribute('aria-expanded', 'true')

      document.querySelectorAll('.f1-step').forEach((step, idx) => {
        step.classList.toggle('active', idx === 2)
      })

      // Show spinner

      driverLoadingSpinner.style.display = ''

      // Load drivers for the selected race (always "Race" session for simplicity)

      fetch('/get_drivers', {
        method: 'POST',

        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },

        body: `year=${yearSel.value}&race=${encodeURIComponent(
          this.value
        )}&session=Race`
      })
        .then((r) => r.json())

        .then((data) => {
          driverLoadingSpinner.style.display = 'none'

          if (data.drivers && data.drivers.length) {
            data.drivers.forEach((driver) => {
              const opt1 = document.createElement('option')

              opt1.value = driver.abbreviation

              opt1.textContent = driver.broadcast_name

              driver1Sel.appendChild(opt1)

              const opt2 = document.createElement('option')

              opt2.value = driver.abbreviation

              opt2.textContent = driver.broadcast_name

              driver2Sel.appendChild(opt2)
            })

            driver1Sel.disabled = false

            driver2Sel.disabled = false

            document

              .getElementById('step2')

              .querySelector('.f1-accordion-header').disabled = false
          }
        })

        .catch(() => {
          driverLoadingSpinner.style.display = 'none'
        })
    })

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

            <strong>Grand Prix:</strong> ${
              raceSel.options[raceSel.selectedIndex].text
            }<br>

            <strong>Driver 1:</strong> ${
              driver1Sel.options[driver1Sel.selectedIndex].text
            }<br>

            <strong>Driver 2:</strong> ${
              driver2Sel.options[driver2Sel.selectedIndex].text
            }

          </div>

        `

        summary.style.display = ''

        submitBtn.disabled = false
      } else {
        summary.style.display = 'none'

        submitBtn.disabled = true
      }
    }

    ;[driver1Sel, driver2Sel].forEach((sel) =>
      sel.addEventListener('change', updateSummary)
    )

    // Prevent same driver selection

    ;[driver1Sel, driver2Sel].forEach((sel) =>
      sel.addEventListener('change', function () {
        if (
          driver1Sel.value &&
          driver2Sel.value &&
          driver1Sel.value === driver2Sel.value
        ) {
          submitBtn.disabled = true

          summary.style.display = 'none'
        }
      })
    )

    // Reset

    resetBtn.addEventListener('click', function () {
      f1Form.reset()

      ;[raceSel, driver1Sel, driver2Sel].forEach((sel) => {
        sel.innerHTML = sel.options[0].outerHTML

        sel.disabled = true
      })

      document.querySelectorAll('.f1-accordion-section').forEach((sec, idx) => {
        sec.setAttribute('aria-expanded', idx === 0 ? 'true' : 'false')

        sec.querySelector('.f1-accordion-header').disabled = idx > 0
      })

      document

        .querySelectorAll('.f1-step')

        .forEach((step, idx) => step.classList.toggle('active', idx === 0))

      summary.style.display = 'none'

      submitBtn.disabled = true
    })

    // On submit, accordion closes and button disables

    document.getElementById('f1Form').addEventListener('submit', function () {
      submitBtn.disabled = true
    })
  }

  // ========== RESULT PAGE LOGIC ==========

  if (document.body.id === 'result-body') {
    // Enhanced chat initialization with context
    function initializeChatWithContext() {
      const raceInfoElement = document.querySelector('.race-info')
      const raceTitle = raceInfoElement ? raceInfoElement.textContent : ''

      const driverTimeElements = document.querySelectorAll('.driver-time .lap-time')
      const driverTimes = Array.from(driverTimeElements)
        .map((el) => el.textContent)
        .join(', ')

      // Store context for chat
      window.currentRaceContext = {
        raceTitle,
        driverTimes,
        plotVisible: document.querySelector('.plot-container img') ? true : false
      }

      // Add context hint to chat after a short delay to ensure chat widget is loaded
      setTimeout(() => {
        const chatWidget = document.getElementById('f1-chat-widget')
        if (chatWidget && !document.querySelector('.chat-context-hint')) {
          const contextHint = document.createElement('div')
          contextHint.className = 'chat-context-hint'
          contextHint.innerHTML = `
            <small style="color: #888; font-size: 12px; display: block; text-align: center; margin: 8px 0;">
              💡 I can analyze the current telemetry plot: ${raceTitle}
            </small>
          `

          // Insert after the chat toggle button
          const chatToggleBtn = document.getElementById('chatToggleBtn')
          if (chatToggleBtn) {
            chatToggleBtn.parentNode.insertBefore(
              contextHint,
              chatToggleBtn.nextSibling
            )
          }
        }
      }, 500)
    }

    // Initialize when page loads
    initializeChatWithContext()

    // Keyboard shortcuts

    document.addEventListener('keydown', function (e) {
      // Check if user is typing in any input, textarea, or contenteditable element

      const activeElement = document.activeElement

      const isTyping =
        activeElement &&
        (activeElement.tagName === 'INPUT' ||
          activeElement.tagName === 'TEXTAREA' ||
          activeElement.tagName === 'SELECT' ||
          activeElement.contentEditable === 'true' ||
          activeElement.closest('#f1-chat-widget')) // Don't trigger when using chat

      // Only trigger shortcuts when NOT typing

      if (!isTyping) {
        // Go back on Escape or Backspace (but not Delete)

        if (e.key === 'Escape' || (e.key === 'Backspace' && !e.shiftKey)) {
          e.preventDefault()

          window.location.href = '/'
        }

        // Print with Ctrl/Cmd+P (more standard)

        if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
          e.preventDefault()

          window.print()
        }

        // Optional: Add 'P' shortcut only with Shift for safety

        if (e.shiftKey && (e.key === 'p' || e.key === 'P')) {
          e.preventDefault()

          window.print()
        }
      }
    })

    // Download PDF functionality

    window.downloadPDF = function () {
      const plotImage = document.querySelector('.plot-container img')

      if (!plotImage) return

      const { jsPDF } = window.jspdf

      const doc = new jsPDF({
        orientation: 'landscape',

        unit: 'mm',

        format: 'a4'
      })

      const imgData = plotImage.src

      const imgWidth = 297 // A4 width in mm

      const imgHeight = 210 // A4 height in mm

      doc.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight)

      doc.setFontSize(12)

      // Safely get race info and driver times

      const raceInfo = document.querySelector('.race-info')

      if (raceInfo) doc.text(raceInfo.textContent, 10, 10)

      const driverTimes = document.querySelectorAll('.driver-time .lap-time')

      if (driverTimes.length > 0) doc.text(driverTimes[0].textContent, 10, 20)

      if (driverTimes.length > 1) doc.text(driverTimes[1].textContent, 10, 30)

      doc.save('f1-telemetry-comparison.pdf')
    }

    // Optional: Hide header on mouse inactivity for even more plot space

    let headerTimeout

    const header = document.querySelector('.header')

    function showHeader() {
      if (!header) return

      header.style.transform = 'translateY(0)'

      clearTimeout(headerTimeout)

      headerTimeout = setTimeout(() => {
        // Uncomment next line if you want auto-hiding header
        // header.style.transform = 'translateY(-100%)';
      }, 3000)
    }

    document.addEventListener('mousemove', showHeader)

    document.addEventListener('keydown', showHeader)
  }
})
