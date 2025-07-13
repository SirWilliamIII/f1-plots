#!/bin/bash
echo "🔍 F1 App Discovery - Working Instance Analysis"
echo "=============================================="
echo "Timestamp: $(date)"
echo "Hostname: $(hostname)"
echo ""

echo "=== 1. CURRENT DOCKER SETUP ==="
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}" 2>/dev/null || echo "Docker not running or not installed"
echo ""

echo "=== 2. DOCKER COMPOSE FILES ==="
find / -name "docker-compose*.yml" -type f 2>/dev/null | head -10
echo ""

echo "=== 3. APP DIRECTORIES ==="
echo "Home directory apps:"
find /home -maxdepth 3 -name "*f1*" -type d 2>/dev/null
find /home -maxdepth 3 -name "*app*" -type d 2>/dev/null
echo ""
echo "System apps:"
find /opt -maxdepth 2 -name "*f1*" -type d 2>/dev/null
find /var -maxdepth 2 -name "*f1*" -type d 2>/dev/null
echo ""
echo "Home directory contents:"
ls -la ~/
echo ""

echo "=== 4. RUNNING PROCESSES ON KEY PORTS ==="
echo "Network listeners:"
sudo netstat -tlnp 2>/dev/null | grep -E ":(80|443|8080|5000|5050|11434)" || ss -tlnp | grep -E ":(80|443|8080|5000|5050|11434)"
echo ""

echo "=== 5. CURRENT WORKING DIRECTORY ==="
echo "PWD: $(pwd)"
ls -la
echo ""

echo "=== 6. CHECK COMMON APP LOCATIONS ==="
for dir in ~/f1-app ~/app ~/f1-race-plots ~/f1plots ~/plot-analysis ~/f1-analysis; do
    if [ -d "$dir" ]; then
        echo "📁 Found directory: $dir"
        echo "Contents:"
        ls -la "$dir" | head -15
        echo ""
        if [ -f "$dir/docker-compose.yml" ] || [ -f "$dir/docker-compose.*.yml" ]; then
            echo "🐳 Docker compose files in $dir:"
            ls -la "$dir"/docker-compose*.yml 2>/dev/null
            echo ""
        fi
        if [ -f "$dir/app.py" ] || [ -f "$dir/main.py" ]; then
            echo "🐍 Python app found in $dir"
            head -20 "$dir/app.py" 2>/dev/null || head -20 "$dir/main.py" 2>/dev/null
            echo ""
        fi
    fi
done

echo "=== 7. GIT REPOSITORIES ==="
for dir in ~/f1-app ~/app ~/f1-race-plots ~/f1plots ~/plot-analysis ~/f1-analysis; do
    if [ -d "$dir/.git" ]; then
        echo "🔗 Git repository in: $dir"
        cd "$dir"
        echo "Remote URLs:"
        git remote -v 2>/dev/null
        echo "Recent commits:"
        git log --oneline -5 2>/dev/null
        echo "Status:"
        git status --porcelain 2>/dev/null
        echo "Current branch:"
        git branch --show-current 2>/dev/null
        echo ""
    fi
done

echo "=== 8. ENVIRONMENT VARIABLES ==="
echo "App-related environment:"
env | grep -iE "(flask|ollama|f1|port|docker|python)" | sort
echo ""

echo "=== 9. SYSTEMD SERVICES ==="
echo "App-related services:"
systemctl list-units --type=service --state=active | grep -iE "(f1|docker|app)" || echo "No matching services found"
echo ""

echo "=== 10. NGINX CONFIGS ==="
if [ -d "/etc/nginx" ]; then
    echo "Nginx configuration files:"
    find /etc/nginx -name "*.conf" 2>/dev/null | head -5
    echo ""
    if [ -f "/etc/nginx/nginx.conf" ]; then
        echo "Main nginx.conf (last 20 lines):"
        tail -20 /etc/nginx/nginx.conf
        echo ""
    fi
fi

echo "=== 11. SSL CERTIFICATES ==="
echo "Certificate files:"
find /home -name "*.pem" -o -name "*.crt" -o -name "*.key" 2>/dev/null | grep -v "/proc\|/sys" | head -10
find /etc -name "*.pem" -o -name "*.crt" -o -name "*.key" 2>/dev/null | head -10
echo ""

echo "=== 12. DOCKER DETAILS ==="
if command -v docker &> /dev/null; then
    echo "Docker version:"
    docker --version
    echo ""
    echo "Docker compose version:"
    docker-compose --version 2>/dev/null || docker compose version 2>/dev/null
    echo ""
    echo "Docker volumes:"
    docker volume ls
    echo ""
    echo "Docker networks:"
    docker network ls
    echo ""
    echo "Docker images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
    echo ""
fi

echo "=== 13. SYSTEM RESOURCES ==="
echo "Memory usage:"
free -h
echo ""
echo "Disk usage:"
df -h
echo ""
echo "CPU info:"
lscpu | grep -E "(Architecture|Model name|CPU\(s\)|Thread|MHz)" 2>/dev/null || echo "lscpu not available"
echo ""
echo "System uptime:"
uptime
echo ""

echo "=== 14. ACTIVE PYTHON PROCESSES ==="
echo "Python processes:"
ps aux | grep python | grep -v grep || echo "No Python processes found"
echo ""

echo "=== 15. WEB SERVER TEST ==="
echo "Testing local web servers:"
for port in 80 443 8080 5000 5050 11434; do
    echo -n "Port $port: "
    curl -s -m 2 -o /dev/null -w "%{http_code}" "http://localhost:$port/" 2>/dev/null || echo "No response"
    echo ""
done

echo ""
echo "🎯 Analysis Complete! $(date)"
echo "=============================================="
