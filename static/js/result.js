// F1 Telemetry Result Page JavaScript
class F1TelemetryApp {
  constructor() {
    this.messages = []
    this.isConnected = false
    this.currentContext = null
    this.init()
  }

  init() {
    this.setupEventListeners()
    this.initializeChat()
    this.setupKeyboardShortcuts()
    this.setupHeaderBehavior()
  }

  setupEventListeners() {
    // Chat toggle
    const chatToggleBtn = document.getElementById('chatToggleBtn')
    if (chatToggleBtn) {
      chatToggleBtn.addEventListener('click', () => this.toggleChat())
    }

    // Send message
    const sendBtn = document.getElementById('sendBtn')
    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.sendMessage())
    }

    // Message input
    const messageInput = document.getElementById('messageInput')
    if (messageInput) {
      messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          this.sendMessage()
        }
      })
    }
  }

  initializeChat() {
    this.checkConnection()
    this.updateWelcomeScreenWithRealData()
  }

  toggleChat() {
    const container = document.getElementById('chatContainer')
    const button = document.getElementById('chatToggleBtn')

    if (container.style.display === 'none' || !container.style.display) {
      container.style.display = 'flex'
      button.style.transform = 'scale(0.9)'
    } else {
      container.style.display = 'none'
      button.style.transform = 'scale(1)'
    }
  }

  closeChat() {
    document.getElementById('chatContainer').style.display = 'none'
    document.getElementById('chatToggleBtn').style.transform = 'scale(1)'
  }

  async checkConnection() {
    const statusDot = document.getElementById('statusDot')
    const statusText = document.getElementById('statusText')
    const offlineMessage = document.getElementById('offlineMessage')
    const inputArea = document.getElementById('inputArea')

    try {
      const response = await fetch('/api/chat/health')
      if (response.ok) {
        this.isConnected = true
        statusDot.style.backgroundColor = '#10b981'
        statusText.textContent = 'AI Ready'
        offlineMessage.style.display = 'none'
        inputArea.style.display = 'block'
      } else {
        throw new Error('Service unavailable')
      }
    } catch (error) {
      this.isConnected = false
      statusDot.style.backgroundColor = '#ef4444'
      statusText.textContent = 'Offline'
      offlineMessage.style.display = 'block'
      inputArea.style.display = 'none'
    }
  }

  async sendMessage() {
    const input = document.getElementById('messageInput')
    const message = input.value.trim()

    if (!message || !this.isConnected) return

    input.value = ''
    this.addMessage('user', message)
    this.showTypingIndicator()

    try {
      const context = window.f1PlotContext
      const questionType = this.determineQuestionType(message, context)
      const prompt = this.buildPrompt(message, questionType, context)

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: prompt })
      })

      this.hideTypingIndicator()

      if (!response.ok) throw new Error('Failed to get response')

      const data = await response.json()
      const formattedResponse = this.formatF1Response(data.response, questionType)
      this.addMessage('ai', formattedResponse, questionType)
    } catch (error) {
      this.hideTypingIndicator()
      this.addMessage('error', 'Sorry, I encountered an error. Please try again.')
    }
  }

  determineQuestionType(message, context) {
    const msg = message.toLowerCase()
    const plotKeywords = [
      'plot',
      'chart',
      'graph',
      'telemetry',
      'this lap',
      'this data',
      'compare',
      'difference',
      'gain',
      'lose',
      'faster',
      'slower'
    ]
    const telemetryKeywords = [
      'throttle',
      'brake',
      'speed',
      'rpm',
      'sector',
      'corner',
      'straight'
    ]

    if (
      context &&
      context.telemetryData &&
      plotKeywords.some((keyword) => msg.includes(keyword))
    ) {
      return 'plot-specific'
    }

    if (
      context &&
      (plotKeywords.some((keyword) => msg.includes(keyword)) ||
        telemetryKeywords.some((keyword) => msg.includes(keyword)))
    ) {
      return 'plot-contextual'
    }

    if (telemetryKeywords.some((keyword) => msg.includes(keyword))) {
      return 'general-telemetry'
    }

    return 'general-f1'
  }

  buildPrompt(userMessage, questionType, context) {
    let prompt =
      'You are an expert Formula 1 analyst and engineer with deep knowledge of telemetry, racing strategy, technical regulations, and driver performance.'

    switch (questionType) {
      case 'plot-specific':
        if (context.telemetryData) {
          const stats = context.telemetryData.statistics
          const biggestGain = context.getBiggestTimeGain()
          const biggestMistake = context.getBiggestMistake()

          prompt += `\n\nYou are analyzing a specific telemetry comparison plot between ${context.driver1} and ${context.driver2} from ${context.race} ${context.session}.

REAL TELEMETRY DATA ACCESS:
- ${context.driver1} Lap Time: ${context.lapTime1}
- ${context.driver2} Lap Time: ${context.lapTime2}

TELEMETRY STATISTICS:
- Max Speed: ${context.driver1} ${stats.max_speed[context.driver1].toFixed(
            1
          )} km/h vs ${context.driver2} ${stats.max_speed[context.driver2].toFixed(
            1
          )} km/h
- Average Speed: ${context.driver1} ${stats.avg_speed[context.driver1].toFixed(
            1
          )} km/h vs ${context.driver2} ${stats.avg_speed[context.driver2].toFixed(
            1
          )} km/h
- Max Brake Pressure: ${context.driver1} ${stats.max_brake_pressure[
            context.driver1
          ].toFixed(1)}% vs ${context.driver2} ${stats.max_brake_pressure[
            context.driver2
          ].toFixed(1)}%
- Full Throttle Time: ${context.driver1} ${stats.max_throttle_time[
            context.driver1
          ].toFixed(1)}s vs ${context.driver2} ${stats.max_throttle_time[
            context.driver2
          ].toFixed(1)}s

KEY ANNOTATIONS FOUND IN PLOT:
${context.annotations
  .slice(0, 5)
  .map(
    (ann) =>
      `- At ${ann.time_seconds.toFixed(1)}s: ${ann.description} (Time delta: ${
        ann.time_gain_loss > 0 ? '+' : ''
      }${ann.time_gain_loss.toFixed(3)}s)`
  )
  .join('\n')}

${
  biggestGain
    ? `BIGGEST TIME DIFFERENCE: At ${biggestGain.time_seconds.toFixed(1)}s - ${
        biggestGain.description
      } (${biggestGain.time_gain_loss.toFixed(3)}s difference)`
    : ''
}

${
  biggestMistake
    ? `MAJOR MISTAKE DETECTED: At ${biggestMistake.time_seconds.toFixed(1)}s - ${
        biggestMistake.description
      }`
    : ''
}

SAMPLED TELEMETRY DATA AVAILABLE: ${
            context.telemetryData.data_points
          } data points sampled every 5 seconds

IMPORTANT: You have access to the ACTUAL telemetry data from this specific plot. Reference these real values and patterns when answering.

User Question: ${userMessage}

Analyze the REAL telemetry data from this plot:`
        } else {
          prompt += `\n\nCURRENT TELEMETRY ANALYSIS CONTEXT:
You are analyzing a specific telemetry comparison plot between ${context.driver1} and ${context.driver2} from ${context.race} ${context.session}.

Plot Details:
- ${context.driver1} Lap Time: ${context.lapTime1}
- ${context.driver2} Lap Time: ${context.lapTime2}
- Channels: Throttle (0-100%), Brakes (0-100%), RPM, Speed (km/h)

IMPORTANT: Only reference patterns and data visible in THIS specific plot. Do not make assumptions about other laps or sessions.

User Question: ${userMessage}

Provide a detailed technical analysis of what you can observe in this telemetry plot:`
        }
        break

      case 'plot-contextual':
        if (context.telemetryData) {
          prompt += `\n\nCONTEXT INFORMATION:
Current telemetry plot: ${context.driver1} vs ${context.driver2} from ${context.race} ${
            context.session
          }
- ${context.driver1} Time: ${context.lapTime1}
- ${context.driver2} Time: ${context.lapTime2}

AVAILABLE REAL DATA:
- Telemetry statistics available for speed, throttle, brake analysis
- ${
            context.annotations ? context.annotations.length : 0
          } key moments annotated in the plot
- Sampled data points every 5 seconds throughout the lap

INSTRUCTIONS: Combine your vast knowledge of Formula 1 data and telemetry to form insights from the current plot data. Reference specific moments, times, and values from this actual telemetry comparison plot between two drivers.

User Question: ${userMessage}

Provide insights using both your F1 knowledge and current plot data:`
        } else {
          prompt += `\n\nCONTEXT INFORMATION:
Current telemetry plot: ${context.driver1} vs ${context.driver2} from ${context.race} ${context.session}
- ${context.driver1} Time: ${context.lapTime1}
- ${context.driver2} Time: ${context.lapTime2}

INSTRUCTIONS: Combine your vast knowledge of Formula 1 data and telemetry with insights from the current plot data. Reference specific moments, times, and values from this actual telemetry comparison plot between two drivers.

User Question: ${userMessage}

Provide insights using both your F1 knowledge and expert level analysis of the current plot context:`
        }
        break

      case 'general-telemetry':
        prompt += `\n\nCONTEXT: We're currently viewing telemetry from ${context.race} with ${context.driver1} vs ${context.driver2}, ensure your answers are relavent to the current context and explain the concepts to a non-expert.

User Question: ${userMessage}

Explain telemetry concepts and techniques in Formula 1:`
        break

      default: // general-f1
        prompt += `\n\nNote: We're currently analyzing ${context.race} data, but this is a general F1 question.

User Question: ${userMessage}

Provide comprehensive F1 knowledge and insights:`
    }

    return prompt
  }

  formatF1Response(response, questionType) {
    let formatted = response

    formatted = formatted.replace(/^([A-Z][^:]*:)/gm, '### $1')
    formatted = formatted.replace(/(\d+\.|\-|\*) /g, '• ')

    const f1Terms = [
      'DRS',
      'ERS',
      'MGU-K',
      'MGU-H',
      'FIA',
      'Formula 1',
      'qualifying',
      'pole position'
    ]
    f1Terms.forEach((term) => {
      const regex = new RegExp(`\\b${term}\\b`, 'gi')
      formatted = formatted.replace(regex, `**${term}**`)
    })

    return formatted
  }

  addMessage(type, content, questionType = null) {
    const messagesContainer = document.getElementById('chatMessages')
    const welcomeScreen = document.getElementById('welcomeScreen')

    if (welcomeScreen) {
      welcomeScreen.style.display = 'none'
    }

    const messageDiv = document.createElement('div')
    messageDiv.style.cssText =
      'display: flex; gap: 8px; margin-bottom: 12px;' +
      (type === 'user' ? 'flex-direction: row-reverse;' : '')

    const avatar = document.createElement('div')
    avatar.style.cssText =
      'width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 14px;'

    if (type === 'user') {
      avatar.style.background = 'linear-gradient(45deg, #06b6d4, #0891b2)'
      avatar.textContent = '👤'
    } else if (type === 'error') {
      avatar.style.background = 'linear-gradient(45deg, #ef4444, #dc2626)'
      avatar.textContent = '⚠️'
    } else {
      const icons = {
        'plot-specific': '📊',
        'plot-contextual': '🔄',
        'general-telemetry': '📈',
        'general-f1': '🏎️'
      }
      avatar.style.background = 'linear-gradient(45deg, #ff0000, #ff6b6b)'
      avatar.textContent = icons[questionType] || '🤖'
    }

    const messageContent = document.createElement('div')
    messageContent.className = 'message-content'
    messageContent.style.cssText =
      'max-width: 85%; padding: 12px 14px; border-radius: 12px; font-size: 13px; line-height: 1.5;'

    if (type === 'user') {
      messageContent.style.cssText +=
        'background: linear-gradient(45deg, #0891b2, #06b6d4); color: white;'
    } else if (type === 'error') {
      messageContent.style.cssText +=
        'background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5;'
    } else {
      messageContent.style.cssText +=
        'background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.95); border: 1px solid rgba(255, 255, 255, 0.1);'
    }

    let formattedContent = content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(
        /### (.*?)$/gm,
        '<h4 style="color: #ff6b6b; margin: 8px 0 4px 0; font-size: 14px;">$1</h4>'
      )
      .replace(/^• (.*?)$/gm, '<li style="margin: 3px 0;">$1</li>')
      .replace(
        /(<li.*?<\/li>)/s,
        '<ul style="margin: 6px 0; padding-left: 18px;">$1</ul>'
      )
      .replace(/\n/g, '<br>')

    messageContent.innerHTML = `
      <div>${formattedContent}</div>
      <div style="font-size: 10px; opacity: 0.6; margin-top: 6px;">${new Date().toLocaleTimeString()}</div>
    `

    messageDiv.appendChild(avatar)
    messageDiv.appendChild(messageContent)
    messagesContainer.appendChild(messageDiv)

    this.messages.push({ type, content, timestamp: new Date(), questionType })
    messagesContainer.scrollTop = messagesContainer.scrollHeight
  }

  showTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages')
    const typingDiv = document.createElement('div')
    typingDiv.id = 'typingIndicator'
    typingDiv.style.cssText = 'display: flex; gap: 8px; margin-bottom: 12px;'

    typingDiv.innerHTML = `
      <div style="width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(45deg, #ff0000, #ff6b6b); display: flex; align-items: center; justify-content: center; font-size: 14px;">🤖</div>
      <div style="max-width: 80%; padding: 10px 12px; border-radius: 12px; font-size: 13px; background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(255, 255, 255, 0.1);">
        <div style="display: flex; align-items: center; gap: 6px; color: rgba(255, 255, 255, 0.6); font-size: 12px;">
          <div style="width: 16px; height: 16px; border: 2px solid rgba(255, 255, 255, 0.2); border-top: 2px solid #ff6b6b; border-radius: 50%; animation: spin 1s linear infinite;"></div>
          <span>Analyzing F1 data...</span>
        </div>
      </div>
    `

    messagesContainer.appendChild(typingDiv)
    messagesContainer.scrollTop = messagesContainer.scrollHeight
  }

  hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator')
    if (indicator) {
      indicator.remove()
    }
  }

  updateWelcomeScreenWithRealData() {
    const context = window.f1PlotContext

    if (!context || !context.telemetryData) return

    const biggestGain = context.getBiggestTimeGain()
    const biggestMistake = context.getBiggestMistake()

    const welcomeScreen = document.getElementById('welcomeScreen')
    if (welcomeScreen) {
      const exampleButtons = welcomeScreen.querySelectorAll(
        'button[onclick*="askQuestion"]'
      )

      if (exampleButtons.length >= 4) {
        exampleButtons[0].onclick = () =>
          this.askQuestion(
            `What is the biggest time gain between ${context.driver1} and ${context.driver2} in this plot?`
            
          )
        exampleButtons[0].textContent = `📊 Where does ${context.driver1} gain time vs ${context.driver2}?`

        exampleButtons[2].onclick = () =>
          this.askQuestion(
            `Analyze the throttle and brake differences between ${context.driver1} and ${context.driver2} in this specific plot`
            `Analyze ${context.driver1} vs ${context.driver2} throttle and brake patterns`
          )
        exampleButtons[2].textContent = `🚦 Analyze ${context.driver1} vs ${context.driver2} throttle/brake patterns`

        if (biggestMistake) {
          exampleButtons[3].onclick = () =>
            this.askQuestion(
              `What happened at ${biggestMistake.time_seconds.toFixed(
                1
              )} seconds in this plot?`
            )
          exampleButtons[3].textContent = `⚠️ What happened at ${biggestMistake.time_seconds.toFixed(
            1
          )}s?`
        }
      }
    }
  }

  askQuestion(question) {
    const input = document.getElementById('messageInput')
    input.value = question
    this.sendMessage()
  }

  clearChat() {
    const messagesContainer = document.getElementById('chatMessages')
    messagesContainer.innerHTML = ''
    const welcomeScreen = document.getElementById('welcomeScreen')
    if (welcomeScreen) {
      welcomeScreen.style.display = 'block'
    }
    this.messages = []
  }

  analyzePlot() {
    const context = window.f1PlotContext
    if (context) {
      this.askQuestion(
        `Analyze this telemetry comparison between ${context.driver1} and ${context.driver2}`
      )
    }
  }

  setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      const activeElement = document.activeElement
      const isTypingInChat =
        activeElement &&
        (activeElement.id === 'messageInput' ||
          activeElement.closest('#f1-chat-widget'))

      if (!isTypingInChat && (e.key === 'Escape' || e.key === 'Backspace')) {
        window.location.href = '/'
      }

      if ((e.metaKey || e.ctrlKey) && e.key === 'p') {
        e.preventDefault()
        window.print()
      }
    })
  }

  setupHeaderBehavior() {
    let headerTimeout
    const header = document.querySelector('.header')

    const showHeader = () => {
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
}

// PDF Download functionality
function downloadPDF() {
  const plotImage = document.querySelector('.plot-container img')
  if (!plotImage) return

  const { jsPDF } = window.jspdf
  const doc = new jsPDF({
    orientation: 'landscape',
    unit: 'mm',
    format: 'a4'
  })

  const imgData = plotImage.src
  const imgWidth = 297
  const imgHeight = 210
  doc.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight)
  doc.setFontSize(12)

  const raceInfo = document.querySelector('.race-info')
  if (raceInfo) doc.text(raceInfo.textContent, 10, 10)

  const driverTimes = document.querySelectorAll('.driver-time')
  if (driverTimes.length > 0) doc.text(driverTimes[0].textContent, 10, 20)
  if (driverTimes.length > 1) doc.text(driverTimes[1].textContent, 10, 30)

  doc.save('f1-telemetry-comparison.pdf')
}

// Global functions for HTML onclick handlers
function toggleChat() {
  window.f1App.toggleChat()
}

function closeChat() {
  window.f1App.closeChat()
}

function sendMessage() {
  window.f1App.sendMessage()
}

function askQuestion(question) {
  window.f1App.askQuestion(question)
}

function clearChat() {
  window.f1App.clearChat()
}

function analyzePlot() {
  window.f1App.analyzePlot()
}

function checkConnection() {
  window.f1App.checkConnection()
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.f1App = new F1TelemetryApp()
})
