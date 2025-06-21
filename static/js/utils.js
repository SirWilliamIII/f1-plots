// F1 Telemetry Utility Functions

class F1Utils {
  static formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(3);
    return minutes > 0 ? `${minutes}:${secs.padStart(6, "0")}` : secs;
  }

  static formatSpeed(kmh) {
    return `${kmh.toFixed(1)} km/h`;
  }

  static formatPercentage(value) {
    return `${value.toFixed(1)}%`;
  }

  static getDriverColor(driverAbbr) {
    const colors = {
      VER: "#0600EF",
      PER: "#0600EF",
      HAM: "#00D2BE",
      RUS: "#00D2BE",
      LEC: "#DC143C",
      SAI: "#DC143C",
      NOR: "#FF8700",
      PIA: "#FF8700",
      ALO: "#006F62",
      STR: "#006F62",
      // Add more driver colors as needed
    };
    return colors[driverAbbr] || "#FFFFFF";
  }

  static debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  static throttle(func, limit) {
    let inThrottle;
    return function () {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }

  static sanitizeHTML(str) {
    const temp = document.createElement("div");
    temp.textContent = str;
    return temp.innerHTML;
  }

  static copyToClipboard(text) {
    if (navigator.clipboard) {
      return navigator.clipboard.writeText(text);
    } else {
      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      return Promise.resolve();
    }
  }

  static showNotification(message, type = "info", duration = 3000) {
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 16px;
      border-radius: 8px;
      color: white;
      font-size: 14px;
      z-index: 10000;
      animation: slideInRight 0.3s ease-out;
      max-width: 300px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;

    // Set background color based on type
    const colors = {
      info: "#3b82f6",
      success: "#10b981",
      warning: "#f59e0b",
      error: "#ef4444",
    };
    notification.style.background = colors[type] || colors.info;

    document.body.appendChild(notification);

    // Auto remove after duration
    setTimeout(() => {
      notification.style.animation = "slideOutRight 0.3s ease-in";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, duration);
  }

  static isValidF1Driver(abbr) {
    const validDrivers = [
      "VER",
      "PER",
      "HAM",
      "RUS",
      "LEC",
      "SAI",
      "NOR",
      "PIA",
      "ALO",
      "STR",
      "TSU",
      "YUK",
      "GAS",
      "OCO",
      "ALB",
      "SAR",
      "MAG",
      "HUL",
      "BOT",
      "ZHO",
    ];
    return validDrivers.includes(abbr.toUpperCase());
  }

  static parseF1Time(timeString) {
    // Parse time strings like "1:23.456" or "23.456"
    const parts = timeString.split(":");
    if (parts.length === 2) {
      return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
    }
    return parseFloat(timeString);
  }

  static calculateTimeDelta(time1, time2) {
    const delta = time1 - time2;
    const sign = delta >= 0 ? "+" : "";
    return `${sign}${delta.toFixed(3)}`;
  }
}

// Export for use in other modules
if (typeof module !== "undefined" && module.exports) {
  module.exports = F1Utils;
} else {
  window.F1Utils = F1Utils;
}
