"""
Plot Serving Routes

Handles serving generated telemetry plots.
"""

import logging
from flask import send_file
from app.plotting.telemetry_plots import get_last_plot_buffer


def register_plot_routes(app):
    """Register plot serving routes"""

    @app.route("/plot.png")
    def serve_plot():
        """Serve the generated telemetry plot"""
        plot_buf = get_last_plot_buffer()
        if plot_buf:
            plot_buf.seek(0)  # Ensure buffer is rewound before sending
            buffer_size = len(plot_buf.getvalue())
            logging.info(f"✅ Serving plot image (size: {buffer_size} bytes)")
            return send_file(plot_buf, mimetype="image/png", as_attachment=False)
        logging.warning("❌ No plot buffer available to serve")
        return "No plot available", 404
