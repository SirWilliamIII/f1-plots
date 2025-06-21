// Error handling and performance monitoring
class F1ErrorHandler {
  constructor() {
    this.setupGlobalErrorHandling();
    this.setupPerformanceMonitoring();
  }

  setupGlobalErrorHandling() {
    window.addEventListener("error", (event) => {
      this.logError("JavaScript Error", {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error,
      });
    });

    window.addEventListener("unhandledrejection", (event) => {
      this.logError("Unhandled Promise Rejection", {
        reason: event.reason,
      });
    });
  }

  setupPerformanceMonitoring() {
    // Monitor page load performance
    window.addEventListener("load", () => {
      setTimeout(() => {
        const perfData = performance.getEntriesByType("navigation")[0];
        this.logPerformance("Page Load", {
          loadTime: perfData.loadEventEnd - perfData.loadEventStart,
          domContentLoaded:
            perfData.domContentLoadedEventEnd -
            perfData.domContentLoadedEventStart,
          totalTime: perfData.loadEventEnd - perfData.fetchStart,
        });
      }, 0);
    });
  }

  logError(type, details) {
    console.error(`[F1 App Error] ${type}:`, details);

    // You could send this to your analytics service
    if (window.gtag) {
      gtag("event", "exception", {
        description: `${type}: ${details.message || details.reason}`,
        fatal: false,
      });
    }
  }

  logPerformance(type, metrics) {
    console.log(`[F1 App Performance] ${type}:`, metrics);

    // You could send this to your analytics service
    if (window.gtag) {
      Object.entries(metrics).forEach(([key, value]) => {
        gtag("event", "timing_complete", {
          name: key,
          value: Math.round(value),
        });
      });
    }
  }
}

// Initialize error handler
document.addEventListener("DOMContentLoaded", () => {
  new F1ErrorHandler();
});
