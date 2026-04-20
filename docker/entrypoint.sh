#!/bin/sh

# ============================================================
# FIX: Remove locale warnings by forcing C locale and disabling
# SSH locale forwarding
# ============================================================

# Create profile script to set locale for all shells
cat > /etc/profile.d/locale.sh << 'EOF'
export LANG=C
export LC_ALL=C
export LANGUAGE=C
EOF
chmod +x /etc/profile.d/locale.sh

# Source it for current session
. /etc/profile.d/locale.sh

# Also set for tnuser's bashrc
su - tnuser -c "echo 'export LANG=C' >> ~/.bashrc"
su - tnuser -c "echo 'export LC_ALL=C' >> ~/.bashrc"
su - tnuser -c "echo 'export LANGUAGE=C' >> ~/.bashrc"

# Prevent SSH from forwarding locale environment variables
if [ -f /etc/ssh/sshd_config ]; then
    # Comment out AcceptEnv lines
    sed -i 's/^AcceptEnv/#AcceptEnv/' /etc/ssh/sshd_config
    # Also remove any existing locale env lines
    sed -i '/^export LANG/d' /etc/profile
    sed -i '/^export LC_ALL/d' /etc/profile
fi

# ============================================================
# Regular entrypoint continues below
# ============================================================

# Ensure data directories exist
mkdir -p /data/notebooks_root
mkdir -p /data/config
mkdir -p /data/nvim
mkdir -p /data/micro

# Create symlink from default config location to /data/config
if [ ! -e /app/source/config ]; then
    ln -s /data/config /app/source/config
    echo "Created symlink: /app/source/config -> /data/config"
fi

# Also symlink for any other config references
if [ ! -e /home/tnuser/.config/terminal-notes ]; then
    mkdir -p /home/tnuser/.config
    ln -s /data/config /home/tnuser/.config/terminal-notes
fi

# Create default config.json if it doesn't exist
if [ ! -f /data/config.json ]; then
    cat > /data/config.json << 'EOF'
{
    "edit": "micro",
    "view": "micro",
    "info": "Available editors: micro, nvim, vim, helix, hx, emacs -nw, nano, kate, geany, gedit, pluma, mousepad, leafpad, mg, jed, joe"
}
EOF
    chown tnuser:tnuser /data/config.json
fi

# Create symlink for config.json if the app expects it in a specific location
if [ ! -f /app/source/config.json ] && [ -f /data/config.json ]; then
    ln -s /data/config.json /app/source/config.json
fi

# Create default micro settings.json if it doesn't exist
if [ ! -f /data/micro/settings.json ]; then
    cat > /data/micro/settings.json << 'EOF'
{
    "autosave": true,
    "autosaveinterval": 30,
    "rmtrailingws": true,
    "savecursor": true,
    "saveundo": true
}
EOF
    chown -R tnuser:tnuser /data/micro
fi

# Set environment variable for micro
export MICRO_CONFIG_HOME=/data/micro

# Create default neovim init.lua if it doesn't exist
if [ ! -f /data/nvim/init.lua ]; then
    cat > /data/nvim/init.lua << 'EOF'
-- Neovim configuration for Terminal Notes
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.expandtab = true
vim.opt.autowriteall = true
vim.opt.updatetime = 30000

vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI", "FocusLost" }, {
    pattern = "*",
    command = "silent! write",
})

print("Neovim autosave enabled")
EOF
    chown -R tnuser:tnuser /data/nvim
fi

# Set environment variable for neovim
export NVIM_APPNAME=/data/nvim

# Fix permissions
chown -R tnuser:tnuser /data
chown -h tnuser:tnuser /app/source/config 2>/dev/null || true
chown -h tnuser:tnuser /app/source/config.json 2>/dev/null || true

# Create symlink for notebooks_root
if [ ! -L /app/source/notebooks_root ]; then
    ln -s /data/notebooks_root /app/source/notebooks_root
    chown -h tnuser:tnuser /app/source/notebooks_root
fi

# Start SSH daemon
/usr/sbin/sshd

# Set up git user
su - tnuser -c "git config --global user.email 'user@example.com'"
su - tnuser -c "git config --global user.name 'Terminal Notes User'"

# Initialize welcome notebook if empty
if [ -z "$(ls -A /data/notebooks_root 2>/dev/null)" ]; then
    echo "Initializing fresh Terminal Notes data directory..."
    mkdir -p /data/notebooks_root/welcome
    
    cat > /data/notebooks_root/welcome/structure.json << 'EOF'
{"id": "welcome", "name": "welcome", "parent_id": null, "notes": [], "subnotebooks": []}
EOF
    echo '{}' > /data/notebooks_root/welcome/notes.json
    echo '{}' > /data/notebooks_root/welcome/files.json
    
    cd /data/notebooks_root/welcome
    git init
    git add .
    git commit -m "initial notebook setup"
    
    chown -R tnuser:tnuser /data/notebooks_root
fi

echo "=========================================="
echo "Terminal Notes Container Started"
echo "Python version: $(python3 --version)"
echo "=========================================="
echo "Configuration:"
echo "  - Config dir (symlink): /app/source/config -> /data/config"
echo "  - Config file: /data/config.json"
echo "  - Neovim config: /data/nvim"
echo "  - Micro config: /data/micro"
echo "  - Notebooks: /data/notebooks_root"
echo "=========================================="
echo "Connect via: ssh tnuser@localhost -p 2222"
echo "Password: tnpass"
echo "Then run: cd /app/source && python3 terminal_notes_ui.py"
echo "=========================================="

tail -f /dev/null