#!/bin/bash
#
# Manage F1 App Services
# Quick commands for controlling systemd services
#

ACTION="${1:-status}"

case "$ACTION" in
    status)
        echo "=== F1 Beam Proxy Status ==="
        sudo systemctl status f1-beam-proxy.service --no-pager -l | head -15
        echo ""
        echo "=== F1 Flask App Status ==="
        sudo systemctl status f1-flask.service --no-pager -l | head -15
        ;;

    start)
        echo "Starting services..."
        sudo systemctl start f1-beam-proxy.service
        sleep 2
        sudo systemctl start f1-flask.service
        sleep 2
        echo "✅ Services started"
        $0 status
        ;;

    stop)
        echo "Stopping services..."
        sudo systemctl stop f1-flask.service
        sudo systemctl stop f1-beam-proxy.service
        echo "✅ Services stopped"
        ;;

    restart)
        echo "Restarting services..."
        sudo systemctl restart f1-beam-proxy.service
        sleep 2
        sudo systemctl restart f1-flask.service
        sleep 2
        echo "✅ Services restarted"
        $0 status
        ;;

    logs)
        SERVICE="${2:-f1-flask}"
        echo "Following logs for $SERVICE.service (Ctrl+C to exit)..."
        sudo journalctl -u $SERVICE.service -f
        ;;

    enable)
        echo "Enabling services to start on boot..."
        sudo systemctl enable f1-beam-proxy.service
        sudo systemctl enable f1-flask.service
        echo "✅ Services enabled"
        ;;

    disable)
        echo "Disabling services from starting on boot..."
        sudo systemctl disable f1-beam-proxy.service
        sudo systemctl disable f1-flask.service
        echo "✅ Services disabled"
        ;;

    health)
        echo "=== Health Check ==="
        echo ""
        echo "Flask (local):"
        curl -s -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" http://localhost:5151/ || echo "❌ Flask not responding"

        echo ""
        echo "Beam Proxy (local):"
        curl -s http://localhost:11435/health | jq -r '"Status: \(.status) | Endpoint: \(.endpoint)"' || echo "❌ Beam proxy not responding"

        echo ""
        echo "Public Site:"
        curl -s -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" https://f1.linux-box.cc/ || echo "❌ Public site not responding"
        ;;

    *)
        echo "F1 App Service Manager"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  status      Show service status (default)"
        echo "  start       Start all services"
        echo "  stop        Stop all services"
        echo "  restart     Restart all services"
        echo "  logs        Follow service logs (default: f1-flask)"
        echo "              Example: $0 logs f1-beam-proxy"
        echo "  enable      Enable services to start on boot"
        echo "  disable     Disable services from starting on boot"
        echo "  health      Check health of all endpoints"
        echo ""
        echo "Examples:"
        echo "  $0                    # Show status"
        echo "  $0 restart            # Restart services"
        echo "  $0 logs f1-flask      # Follow Flask logs"
        echo "  $0 health             # Check all endpoints"
        ;;
esac
