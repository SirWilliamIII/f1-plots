"""
Plot Serving Routes

Handles serving generated telemetry plots.
"""

import logging
from flask import send_file
from app.plotting.telemetry_plots import get_last_plot_buffer
from app.error_tracking.error_tracker import get_error_tracker, ErrorSeverity


def register_plot_routes(app):
    """Register plot serving routes"""

    @app.route("/plot.png")
    def serve_plot():
        """Serve the generated telemetry plot"""
        try:
            plot_buf = get_last_plot_buffer()
            if plot_buf:
                plot_buf.seek(0)  # Ensure buffer is rewound before sending
                buffer_size = len(plot_buf.getvalue())
                logging.info(f"✅ Serving plot image (size: {buffer_size} bytes)")
                return send_file(plot_buf, mimetype="image/png", as_attachment=False)

            # No plot available - track as warning
            error_tracker = get_error_tracker()
            error_tracker.capture_message(
                "Plot request failed: No plot buffer available",
                level=ErrorSeverity.WARNING,
                context={'endpoint': '/plot.png'}
            )
            logging.warning("❌ No plot buffer available to serve")
            return "No plot available", 404

        except Exception as e:
            # Track plot serving errors
            error_tracker = get_error_tracker()
            error_tracker.capture_exception(
                e,
                context={
                    'operation': 'serve_plot',
                    'endpoint': '/plot.png'
                },
                level=ErrorSeverity.ERROR
            )
            logging.error(f"Failed to serve plot: {e}", exc_info=True)
            return "Failed to serve plot", 500
