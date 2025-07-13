#!/bin/bash

# Oracle Server Factory Reset Script
# This script returns the server to a fresh, minimal state
# WARNING: This removes ALL user-installed software except SSH

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${RED}🚨 ORACLE SERVER FACTORY RESET 🚨${NC}"
echo -e "${YELLOW}This will remove EVERYTHING except core Ubuntu and SSH${NC}"
echo ""

# Critical safety warning
echo -e "${RED}⚠️  EXTREME WARNING ⚠️${NC}"
echo "This script will:"
echo "• Remove Docker completely"
echo "• Remove Python packages and environments"
echo "• Remove nginx, Ollama, and all web services"
echo "• Remove ALL application files"
echo "• Remove ALL user-installed packages"
echo "• Reset the server to minimal Ubuntu state"
echo ""
echo -e "${GREEN}This script will PRESERVE:${NC}"
echo "• SSH access and configuration (~/.ssh directory)"
echo "• SSH authorized_keys file"
echo "• Network configuration"
echo "• Oracle Cloud Agent"
echo "• Basic Ubuntu system packages"
echo "• Your ability to reconnect via SSH"
echo ""
echo -e "${RED}THIS CANNOT BE UNDONE!${NC}"
echo ""
read -p "Type 'FACTORY RESET' to confirm: " -r
if [[ ! $REPLY == "FACTORY RESET" ]]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
read -p "Are you ABSOLUTELY SURE? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Starting factory reset...${NC}"
sleep 3

# Record current package state for comparison
echo -e "${YELLOW}Recording initial state...${NC}"
dpkg --get-selections > /tmp/initial-packages.txt

# 1. Stop ALL services except critical ones
echo -e "${MAGENTA}Phase 1: Stopping all services...${NC}"

# Stop web services
sudo systemctl stop nginx apache2 httpd 2>/dev/null || true
sudo systemctl disable nginx apache2 httpd 2>/dev/null || true

# Stop application services
sudo pkill -f gunicorn || true
sudo pkill -f python || true
sudo pkill -f node || true
sudo pkill -f java || true

# Stop Docker
sudo systemctl stop docker 2>/dev/null || true
sudo systemctl disable docker 2>/dev/null || true

# Stop Ollama
sudo systemctl stop ollama 2>/dev/null || true
sudo systemctl disable ollama 2>/dev/null || true
sudo pkill -f ollama || true

echo -e "${GREEN}✅ Services stopped${NC}"

# 2. Remove Docker completely
echo -e "${MAGENTA}Phase 2: Removing Docker...${NC}"

# Kill all Docker processes
sudo pkill -f docker || true

# Remove all Docker data
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true
docker rmi -f $(docker images -aq) 2>/dev/null || true
docker volume rm $(docker volume ls -q) 2>/dev/null || true
docker network rm $(docker network ls -q) 2>/dev/null || true

# Uninstall Docker packages
sudo apt-get remove -y docker docker-engine docker.io containerd runc docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true
sudo apt-get purge -y docker docker-engine docker.io containerd runc docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || true

# Remove Docker directories
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd
sudo rm -rf /etc/docker
sudo rm -rf /var/run/docker.sock
sudo rm -rf /usr/local/bin/docker-compose

echo -e "${GREEN}✅ Docker removed${NC}"

# 3. Remove programming environments
echo -e "${MAGENTA}Phase 3: Removing programming environments...${NC}"

# Remove Python environments and packages
sudo pip uninstall -y --break-system-packages $(pip list --format=freeze | cut -d'=' -f1) 2>/dev/null || true
sudo apt-get remove -y python3-pip python3-venv python3-dev 2>/dev/null || true
rm -rf ~/.local/lib/python*
rm -rf ~/venv
rm -rf ~/.cache/pip

# Remove Node.js
sudo apt-get remove -y nodejs npm 2>/dev/null || true
rm -rf ~/.npm
rm -rf ~/.nvm
rm -rf /usr/lib/node_modules

# Remove other development tools
sudo apt-get remove -y build-essential git curl wget 2>/dev/null || true

echo -e "${GREEN}✅ Programming environments removed${NC}"

# 4. Remove web servers and services
echo -e "${MAGENTA}Phase 4: Removing web services...${NC}"

# Remove nginx
sudo apt-get remove -y nginx nginx-common nginx-core 2>/dev/null || true
sudo apt-get purge -y nginx nginx-common nginx-core 2>/dev/null || true
sudo rm -rf /etc/nginx
sudo rm -rf /var/log/nginx
sudo rm -rf /var/www

# Remove Apache if present
sudo apt-get remove -y apache2 2>/dev/null || true
sudo apt-get purge -y apache2 2>/dev/null || true

echo -e "${GREEN}✅ Web services removed${NC}"

# 5. Remove Ollama completely
echo -e "${MAGENTA}Phase 5: Removing Ollama...${NC}"

# Uninstall Ollama
sudo rm -rf /usr/local/bin/ollama
sudo rm -rf /usr/share/ollama
sudo rm -rf /var/lib/ollama
sudo rm -rf ~/.ollama
sudo userdel ollama 2>/dev/null || true
sudo groupdel ollama 2>/dev/null || true

echo -e "${GREEN}✅ Ollama removed${NC}"

# 6. Clean ALL application files
echo -e "${MAGENTA}Phase 6: Cleaning all application files...${NC}"

# Remove all application directories
rm -rf ~/f1-*
rm -rf ~/app*
rm -rf ~/project*
rm -rf ~/deploy*
rm -rf ~/test*
rm -rf ~/tmp*
rm -rf ~/.cache/*
rm -rf ~/.local/share/applications/*

# Clean opt directory
sudo rm -rf /opt/*

# Clean home directory of scripts and configs (but preserve SSH keys)
# IMPORTANT: Preserving .ssh directory and all SSH configurations
find ~ -maxdepth 1 -name "*.sh" ! -name ".bashrc" ! -name ".profile" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.py" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.yml" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.yaml" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.json" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.log" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.tar.gz" -delete 2>/dev/null || true
find ~ -maxdepth 1 -name "*.zip" -delete 2>/dev/null || true

# CRITICAL: Preserve SSH directory
echo "• Preserving ~/.ssh directory and all SSH keys"

echo -e "${GREEN}✅ Application files cleaned${NC}"

# 7. Remove all non-essential packages
echo -e "${MAGENTA}Phase 7: Removing non-essential packages...${NC}"

# Get list of manually installed packages
comm -23 <(apt-mark showmanual | sort) <(gzip -dc /var/log/installer/initial-status.gz | sed -n 's/^Package: //p' | sort) > /tmp/manual-packages.txt 2>/dev/null || true

# Remove packages that are safe to remove
while IFS= read -r package; do
    case "$package" in
        openssh-*|ssh|libssh*|cloud-init|oracle-cloud-agent|systemd*|network*|ubuntu-minimal|ubuntu-standard|linux-*|sudo|passwd|adduser|base-files|base-passwd|bash|coreutils|dash|diffutils|dpkg|e2fsprogs|findutils|grep|gzip|hostname|init|libc-bin|login|mount|ncurses-*|perl-base|sed|tar|util-linux|ca-certificates)
            # Skip critical packages including SSH dependencies
            ;;
        *)
            sudo apt-get remove -y "$package" 2>/dev/null || true
            ;;
    esac
done < /tmp/manual-packages.txt

echo -e "${GREEN}✅ Non-essential packages removed${NC}"

# 8. Clean package system
echo -e "${MAGENTA}Phase 8: Cleaning package system...${NC}"

sudo apt-get autoremove -y
sudo apt-get autoclean
sudo apt-get clean
sudo apt-get update

echo -e "${GREEN}✅ Package system cleaned${NC}"

# 9. Clean system files
echo -e "${MAGENTA}Phase 9: Cleaning system files...${NC}"

# Clean logs (but keep system logs)
sudo find /var/log -type f -name "*.log" -exec truncate -s 0 {} \; 2>/dev/null || true
sudo rm -rf /var/log/journal/*

# Clean temp files
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*

# Clean caches
sudo rm -rf /var/cache/apt/archives/*
sudo rm -rf /var/cache/snapd/*

# Reset bash history
history -c
> ~/.bash_history

# CRITICAL: Verify SSH configuration is intact
echo -e "${YELLOW}Verifying SSH configuration...${NC}"
if [ -d ~/.ssh ] && [ -f ~/.ssh/authorized_keys ]; then
    echo -e "${GREEN}✅ SSH directory and authorized_keys preserved${NC}"
    chmod 700 ~/.ssh
    chmod 600 ~/.ssh/authorized_keys
else
    echo -e "${RED}⚠️  WARNING: SSH configuration may be damaged!${NC}"
fi

echo -e "${GREEN}✅ System files cleaned${NC}"

# 10. Reset systemd services
echo -e "${MAGENTA}Phase 10: Resetting systemd...${NC}"

# Remove all custom service files
sudo find /etc/systemd/system -name "*.service" -type f ! -name "ssh*" ! -name "oracle*" ! -name "cloud*" -delete 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo -e "${GREEN}✅ Systemd reset${NC}"

# 11. Final cleanup
echo -e "${MAGENTA}Phase 11: Final cleanup...${NC}"

# Remove any remaining custom configurations
sudo rm -rf /usr/local/bin/* 2>/dev/null || true
sudo rm -rf /usr/local/sbin/* 2>/dev/null || true
sudo rm -rf /usr/local/lib/* 2>/dev/null || true
sudo rm -rf /usr/local/share/* 2>/dev/null || true

# Reset user environment (but preserve PATH for SSH)
cp /etc/skel/.bashrc ~/.bashrc
cp /etc/skel/.profile ~/.profile

# Ensure SSH remains in PATH
if ! grep -q "/usr/bin/ssh" ~/.profile; then
    echo 'export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' >> ~/.profile
fi

echo -e "${GREEN}✅ Final cleanup complete${NC}"

# Summary
echo ""
echo -e "${GREEN}🎉 FACTORY RESET COMPLETE! 🎉${NC}"
echo ""
echo -e "${BLUE}System Status:${NC}"
echo "• Ubuntu Version: $(lsb_release -d | cut -f2)"
echo "• Kernel: $(uname -r)"
echo "• Memory: $(free -h | grep Mem | awk '{print $2}')"
echo "• Disk Usage:"
df -h | grep -E "^/dev|^Filesystem"
echo ""
echo -e "${YELLOW}Remaining Packages:${NC}"
dpkg --get-selections | wc -l
echo ""
echo -e "${GREEN}Your Oracle server is now in a minimal, factory-fresh state!${NC}"
echo ""
echo "To reconnect:"
echo "ssh -i ~/.ssh/will-oracle-aarch64.key ubuntu@141.147.101.95"
echo ""
echo -e "${BLUE}The server only has:${NC}"
echo "• Basic Ubuntu system"
echo "• SSH server"
echo "• Oracle Cloud Agent"
echo "• Network configuration"
echo ""
echo -e "${YELLOW}You'll need to reinstall everything from scratch for your next deployment.${NC}"