#!/bin/bash
# Quick management script for Oracle deployment

APP_DIR="/opt/f1-app"

case "$1" in
    status)
        echo "🔍 Checking service status..."
        sudo systemctl status f1-modal-proxy f1-app
        ;;

    logs)
        echo "📋 Viewing logs (Ctrl+C to exit)..."
        if [ "$2" = "proxy" ]; then
            sudo journalctl -u f1-modal-proxy -f
        elif [ "$2" = "app" ]; then
            sudo journalctl -u f1-app -f
        else
            echo "Live logs: sudo journalctl -u f1-app -f"
            echo "Recent logs:"
            sudo journalctl -u f1-app -n 30
        fi
        ;;

    restart)
        echo "🔄 Restarting services..."
        sudo systemctl restart f1-modal-proxy
        sleep 2
        sudo systemctl restart f1-app
        echo "✓ Services restarted"
        ;;

    update)
        echo "📥 Updating application..."
        cd $APP_DIR
        sudo git pull
        sudo systemctl restart f1-app
        echo "✓ Application updated and restarted"
        ;;

    health)
        echo "🏥 Health checks..."
        echo ""
        echo "Modal Proxy:"
        curl -s http://localhost:11435/health | jq .
        echo ""
        echo "Flask App:"
        curl -s http://localhost:5151/health | jq .
        ;;

    modal)
        echo "☁️  Modal GPU status..."
        modal app list
        ;;

    backup)
        echo "💾 Creating backup..."
        BACKUP_FILE="f1-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
        sudo tar -czf ~/$BACKUP_FILE \
            $APP_DIR/.env \
            $APP_DIR/fastf1_cache \
            --exclude=$APP_DIR/fastf1_cache/*.tmp
        echo "✓ Backup created: ~/$BACKUP_FILE"
        ;;

    ssl)
        if [ -z "$2" ]; then
            echo "Usage: $0 ssl <domain.com>"
            exit 1
        fi
        echo "🔒 Setting up SSL for $2..."
        sudo certbot --nginx -d $2
        ;;

    *)
        echo "F1 App Oracle Management"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  status     - Check service status"
        echo "  logs       - View application logs"
        echo "  logs app   - View Flask logs"
        echo "  logs proxy - View Modal proxy logs"
        echo "  restart    - Restart all services"
        echo "  update     - Pull latest code and restart"
        echo "  health     - Run health checks"
        echo "  modal      - Check Modal GPU status"
        echo "  backup     - Backup environment and cache"
        echo "  ssl <domain> - Setup SSL certificate"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  $0 logs app"
        echo "  $0 restart"
        echo "  $0 ssl f1.example.com"
        ;;
esac
